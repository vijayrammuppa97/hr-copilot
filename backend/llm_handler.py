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

_BASE_SYSTEM_PROMPT = """\
You are a friendly, knowledgeable HR Onboarding Assistant. \
Help employees navigate their onboarding journey using the context provided.

- Respond naturally and conversationally — like a warm, helpful colleague, not a FAQ page.
- Use plain sentences; only use bullet points when listing several distinct items is genuinely clearer.
- Address the employee by their first name occasionally to keep it personal.
- Reference earlier parts of the conversation when it adds context.
- Never invent policies or process steps not provided to you.
- Keep responses focused: 2-4 sentences for simple questions, a short paragraph for complex ones.
- If they seem frustrated or explicitly ask for a human, acknowledge it warmly and tell them \
  to click the "Get Human Help" button or you can note their escalation.
- If something requires official HR confirmation, say so honestly.
- Close with a natural offer to help with the next step.
"""

_GENERAL_HR_PROMPT = """\
You are a friendly, knowledgeable HR colleague. Help employees understand company policies \
using ONLY the <policy_context> provided.

- Respond naturally and conversationally — not as a list of rules.
- Use plain sentences; only use bullet points when listing multiple distinct items makes things clearer.
- Reference what was said earlier in the conversation when relevant.
- Never invent or assume policies not present in the context.
- Keep responses focused — 2-4 sentences for simple questions, a short paragraph for complex ones.
- End each response with a brief, natural offer to help further or a pointer to hr@company.com for confirmation.
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
        case_context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens from Ollama one chunk at a time."""
        if case_context:
            system_content = f"{_BASE_SYSTEM_PROMPT}\n\n{case_context}"
        else:
            system_content = _GENERAL_HR_PROMPT

        kb_block = self._build_kb_block(kb_context)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": f"{user_message}\n\n{kb_block}" if kb_block else user_message})

        async for chunk in await self._client.chat(
            model=self._model,
            messages=messages,
            options={"num_predict": 600, "temperature": 0.45, "num_ctx": 4096},
            stream=True,
        ):
            token = chunk.message.content
            if token:
                yield token

    def _build_kb_block(self, results: list[dict]) -> str:
        if not results:
            return ""
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
