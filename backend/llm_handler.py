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

STRICT GROUNDING RULES — you MUST follow every rule below:
1. Read every section inside <policy_context> carefully before responding.
2. Your answer MUST be directly supported by text in those sections.
3. Quote or closely paraphrase the exact policy wording when possible.
4. If the answer is not present in the context, say EXACTLY:
   "I could not find that information in our HR policy. Please contact HR at hr@company.com."
5. NEVER use your own training knowledge about HR, employment law, or any company policy.
6. NEVER guess, infer, or say "typically" / "usually" — only state what the policy explicitly says.
7. NEVER mix information from different sections unless both sections are relevant to the question.
8. At the end of your answer, cite the section(s) you used, e.g. "Source: 1.10 Paternity Leave".
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
    ) -> AsyncGenerator[str, None]:
        system_content = (
            f"{_ONBOARDING_SYSTEM}\n\n{case_context}" if case_context
            else _GENERAL_HR_SYSTEM
        )

        kb_block = self._build_kb_block(kb_context)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        for turn in history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        user_content = f"{user_message}\n\n{kb_block}" if kb_block else user_message
        messages.append({"role": "user", "content": user_content})

        async for chunk in await self._client.chat(
            model=self._model,
            messages=messages,
            options={
                "num_predict": 400,
                "temperature": 0.05,
                "num_ctx":     3072,
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
            content = r["content"][:600]
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
