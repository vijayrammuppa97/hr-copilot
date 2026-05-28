"""
Handles all communication with the local Ollama LLM server.

Ollama runs models locally (no API key required).
Default model: llama3.2 — change via OLLAMA_MODEL env var.
Ollama must be running: https://ollama.com
"""

import logging

import ollama

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
    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434") -> None:
        self._model = model
        self._client = ollama.AsyncClient(host=host)
        logger.info("LLMHandler initialised — model=%s host=%s", model, host)

    async def generate(
        self,
        user_message: str,
        kb_context: list[dict],
        history: list[dict[str, str]],
    ) -> tuple[str, float]:
        """
        Call Ollama and return (response_text, confidence_score).

        confidence_score is a heuristic derived from KB hit count.
        """
        context_block = self._build_context(kb_context)
        confidence = self._estimate_confidence(kb_context)

        # Build messages: system prompt → prior history → current user message
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
        ]
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": f"{user_message}\n\n{context_block}"})

        response = await self._client.chat(
            model=self._model,
            messages=messages,
            options={"num_predict": 400, "temperature": 0.3, "num_ctx": 2048},
            stream=False,
        )

        answer = response.message.content.strip()
        logger.debug("model=%s confidence=%.2f", self._model, confidence)
        return answer, confidence

    def _build_context(self, results: list[dict]) -> str:
        if not results:
            return "<policy_context>No matching policy sections found for this query.</policy_context>"
        parts = [f"### {r['section']}\n{r['content']}" for r in results[:3]]
        body = "\n\n".join(parts)
        return f"<policy_context>\n{body}\n</policy_context>"

    def _estimate_confidence(self, results: list[dict]) -> float:
        if not results:
            return 0.20
        mapping = {1: 0.60, 2: 0.75, 3: 0.85, 4: 0.90}
        return mapping.get(len(results), 0.92)
