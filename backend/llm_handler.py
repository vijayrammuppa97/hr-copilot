"""
Handles all communication with the local Ollama LLM server.

Ollama runs models locally (no API key required).
Default model: llama3.2 — change via OLLAMA_MODEL env var.
Ollama must be running: https://ollama.com
"""

import logging
from collections.abc import AsyncGenerator

import ollama

logger = logging.getLogger("hr_copilot.llm")

_SYSTEM_PROMPT = """\
You are a friendly, knowledgeable HR colleague. Help employees understand company policies \
using ONLY the <policy_context> provided.

- Respond naturally and conversationally — like a helpful colleague, not a FAQ page.
- Use plain sentences. Only use bullet points when listing several distinct items is genuinely clearer.
- Reference earlier parts of the conversation when it adds context.
- Never invent or assume policies not in the context.
- Keep answers focused: 2-4 sentences for simple questions, a short paragraph for complex ones.
- Close with a natural offer to help further, or note they can confirm details at hr@company.com.
- If the topic is not covered, say so naturally and direct them to hr@company.com.
"""


class LLMHandler:
    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434") -> None:
        self._model = model
        self._client = ollama.AsyncClient(host=host)
        logger.info("LLMHandler initialised — model=%s host=%s", model, host)

    async def stream(
        self,
        user_message: str,
        kb_context: list[dict],
        history: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens from Ollama one chunk at a time."""
        context_block = self._build_context(kb_context)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
        ]
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": f"{user_message}\n\n{context_block}"})

        async for chunk in await self._client.chat(
            model=self._model,
            messages=messages,
            options={"num_predict": 600, "temperature": 0.45, "num_ctx": 4096},
            stream=True,
        ):
            token = chunk.message.content
            if token:
                yield token

    def _build_context(self, results: list[dict]) -> str:
        if not results:
            return "<policy_context>No matching policy sections found.</policy_context>"
        parts = []
        for r in results[:3]:
            content = r["content"][:500]
            parts.append(f"[{r['section']}]\n{content}")
        return f"<policy_context>\n{'---'.join(parts)}\n</policy_context>"

    def estimate_confidence(self, results: list[dict]) -> float:
        if not results:
            return 0.20
        mapping = {1: 0.60, 2: 0.75, 3: 0.85, 4: 0.90}
        return mapping.get(len(results), 0.92)
