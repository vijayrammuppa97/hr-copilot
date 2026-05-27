"""
Handles all communication with the Claude API via the Anthropic SDK.

Key design decisions:
- System prompt is marked ephemeral for prompt caching (reduces latency on
  repeated calls with the same system prompt).
- Conversation history is limited upstream; this module accepts whatever
  slice it receives and passes it verbatim.
- Confidence is estimated heuristically from KB hit count — no model call.
"""

import logging
from typing import Any

import anthropic

logger = logging.getLogger("hr_copilot.llm")

_SYSTEM_PROMPT = """\
You are an expert HR Knowledge Copilot for a large enterprise organization. \
Your role is to provide accurate, helpful, and empathetic responses to employee \
questions about company HR policies and procedures.

## Core guidelines
1. **Accuracy** — Answer only from the <policy_context> provided. Never invent \
policies or figures.
2. **Clarity** — Use plain language and structure answers with bullet points or \
numbered steps when appropriate.
3. **Empathy** — HR questions can be sensitive. Always be respectful and supportive.
4. **Escalation** — For matters requiring confidential HR judgement, direct the \
employee to HR (hr@company.com) or their HR Business Partner.
5. **Boundaries** — Do not provide legal advice. Recommend HR/Legal consultation \
for complex legal matters.
6. **Completeness** — Be thorough but concise. Cite the policy section when \
referencing a specific rule (e.g., "Per Section 3.2 — Remote Work Eligibility…").

## Response format
- Start directly with the answer. No preamble like "Based on the policy…".
- Use bullet lists for multi-step processes.
- Close with: "For further assistance, contact HR at hr@company.com or speak \
with your HR Business Partner."
- If the question is outside the provided context, respond: "I don't have \
specific information on that topic. Please contact HR directly at \
hr@company.com."
"""


class LLMHandler:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is not set — LLM calls will fail")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def generate(
        self,
        user_message: str,
        kb_context: list[dict],
        history: list[dict[str, str]],
    ) -> tuple[str, float]:
        """
        Call Claude and return (response_text, confidence_score).

        confidence_score is a [0, 1] heuristic derived from how many KB
        sections matched the query; it is not a model-reported probability.
        """
        context_block = self._build_context(kb_context)
        confidence = self._estimate_confidence(kb_context)

        # Build the messages array: prior turns + current user message
        messages: list[dict[str, Any]] = [
            {"role": m["role"], "content": m["content"]} for m in history
        ]
        messages.append(
            {
                "role": "user",
                "content": f"{user_message}\n\n{context_block}",
            }
        )

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            # Cache the static system prompt to reduce time-to-first-token
            # on subsequent requests (requires anthropic SDK >= 0.28).
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )

        answer = response.content[0].text.strip()
        logger.debug(
            "model=%s tokens_in=%s tokens_out=%s confidence=%.2f",
            self._model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            confidence,
        )
        return answer, confidence

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _build_context(self, results: list[dict]) -> str:
        if not results:
            return "<policy_context>No matching policy sections found for this query.</policy_context>"

        parts = [f"### {r['section']}\n{r['content']}" for r in results[:5]]
        body = "\n\n".join(parts)
        return f"<policy_context>\n{body}\n</policy_context>"

    def _estimate_confidence(self, results: list[dict]) -> float:
        """Heuristic: more KB hits → higher confidence."""
        if not results:
            return 0.20
        mapping = {1: 0.60, 2: 0.75, 3: 0.85, 4: 0.90}
        return mapping.get(len(results), 0.92)
