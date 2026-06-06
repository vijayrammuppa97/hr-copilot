"""
LLM handler — Ollama streaming with strict RAG grounding.

Retrieval config:
  - Top 8 chunks passed to the LLM
  - 600 chars per chunk (up from 200/500)
  - Similarity threshold enforced upstream in knowledge_loader
  - keep_alive=-1 keeps both llama3.2 and nomic-embed-text in Ollama RAM

Grounding rules:
  - Temperature 0.05 — near-deterministic
  - System prompt explicitly forbids answering outside context
  - Retrieved section titles are listed so the LLM can cite them
"""

import logging
from collections.abc import AsyncGenerator

import ollama

logger = logging.getLogger("hr_copilot.llm")


# ── System prompts ────────────────────────────────────────────────────────── #

_GROUNDING_RULES = """\

STRICT GROUNDING RULES — follow every rule below:
1. Read ALL sections inside <policy_context> carefully before responding.
2. Your answer MUST be grounded in those sections — do not invent policy details.
3. PERSONAL CONTEXT + CALCULATIONS: When the user tells you their situation
   (years of service, employment type, part-time hours, etc.), USE that information
   to calculate their specific entitlement from the policy tables.
   Example: user says "I have 3 years of service" + policy says "2–5 years = 18 days"
   → answer "You are entitled to 18 days of annual leave."
   Always show the reasoning: which tier they fall into and why.
4. CROSS-REFERENCE: Combine information from multiple sections when needed to give
   a complete answer. For example, mental health days come from the sick leave balance,
   so reference both sections when relevant.
5. DO perform arithmetic when applying policy rules (pro-rating, accrual, tenure tiers).
6. If the answer is genuinely not in the context, say EXACTLY:
   "I could not find that information in our HR policy. Please contact HR at hr@company.com."
7. NEVER use training knowledge about HR law or generic HR practice — only the policy.
8. At the end, cite ALL sections used. Example: "Source: 1.2 Annual Leave Days by Tenure, 1.8 Mental Health Days"
"""

_ONBOARDING_SYSTEM = "You are an HR Onboarding Assistant for Acme." + _GROUNDING_RULES
_GENERAL_HR_SYSTEM  = "You are an HR Policy Assistant for Acme." + _GROUNDING_RULES


class LLMHandler:
    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434") -> None:
        self._model  = model
        self._client = ollama.AsyncClient(host=host)
        logger.info("LLMHandler initialised — model=%s host=%s", model, host)

    async def stream(
        self,
        user_message: str,
        kb_context: list[dict],
        history: list[dict[str, str]],
        case_context: str | None = None,
        user_profile: str | None = None,
    ) -> AsyncGenerator[str, None]:
        system_content = (
            f"{_ONBOARDING_SYSTEM}\n\n{case_context}" if case_context
            else _GENERAL_HR_SYSTEM
        )

        kb_block = self._build_kb_block(kb_context)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        for turn in history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        # Silently prepend the stored profile so the LLM always knows who it's talking to.
        # Placed before the user message so it doesn't alter the conversational tone.
        if user_profile:
            effective_message = f"{user_profile}\n\n{user_message}"
        else:
            effective_message = user_message

        user_content = f"{effective_message}\n\n{kb_block}" if kb_block else effective_message
        messages.append({"role": "user", "content": user_content})


        async for chunk in await self._client.chat(
            model=self._model,
            messages=messages,
            options={
                "num_predict": 400,
                "temperature": 0.05,
                "num_ctx":     8192,
                "top_p":       0.9,
                "repeat_penalty": 1.1,
            },
            keep_alive=-1,
            stream=True,
        ):
            token = chunk.message.content
            if token:
                yield token

    def _build_kb_block(self, results: list[dict]) -> str:
        """
        Build the context block injected into every user message.
        - Top 8 chunks
        - 600 chars per chunk
        - Section title listed explicitly so the LLM can cite it
        """
        if not results:
            return (
                "<policy_context>\n"
                "No relevant policy sections were found for this query.\n"
                "If asked, tell the user you could not find that information.\n"
                "</policy_context>"
            )

        section_list = ", ".join(r["section"] for r in results[:8])
        parts = []
        for i, r in enumerate(results[:8]):
            heading = r["section"]
            content = r["content"]          # full chunk — no truncation
            score   = r.get("score", 0.0)
            parts.append(f"[Section {i+1}: {heading} | relevance={score:.3f}]\n{content}")

        joined = "\n\n---\n\n".join(parts)
        return (
            f"<policy_context>\n"
            f"Retrieved sections: {section_list}\n\n"
            f"{joined}\n"
            f"</policy_context>"
        )

    def estimate_confidence(self, results: list[dict]) -> float:
        """
        Real confidence score based on actual semantic similarity.
        Uses the top result's score rather than a fake lookup table.
        """
        if not results:
            return 0.0
        scores = [r.get("score", 0.0) for r in results if "score" in r]
        if not scores:
            # Fallback if scores not populated (keyword-only search)
            return round(0.3 + min(len(results), 5) * 0.08, 2)
        top_score = max(scores)
        avg_score = sum(scores[:3]) / min(len(scores), 3)
        # Blend top and average — prevents single outlier from inflating confidence
        return round((0.6 * top_score + 0.4 * avg_score), 3)
