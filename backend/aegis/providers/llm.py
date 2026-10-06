"""LLM provider: Featherless via its OpenAI-compatible API.

- One shared async client; a semaphore caps concurrent requests (Featherless
  plans limit concurrency per account).
- `chat_json` forces JSON mode and tolerates fenced or prefixed output.
- Every caller treats the result as untrusted and validates it.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from ..core.config import Settings


class LLMUnavailable(RuntimeError):
    """No backend configured (no API key)."""


class LLMBadOutput(ValueError):
    """The model answered, but not with a usable JSON object."""


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> dict:
    """Pull one JSON object out of a model reply. Raises LLMBadOutput."""
    t = _FENCE.sub("", (text or "").strip())
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            raise LLMBadOutput(f"no JSON object in model output: {t[:200]!r}") from None
        try:
            data = json.loads(t[start:end + 1])
        except json.JSONDecodeError as e:
            raise LLMBadOutput(f"invalid JSON in model output: {t[:200]!r}") from e
    if not isinstance(data, dict):
        raise LLMBadOutput("model output is not a JSON object")
    return data


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._sem = asyncio.Semaphore(max(1, settings.llm_max_concurrency))

    @property
    def configured(self) -> bool:
        return self.settings.llm_configured

    def _get(self):
        if not self.configured:
            raise LLMUnavailable("FEATHERLESS_API_KEY is not set")
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(base_url=self.settings.llm_base_url,
                                       api_key=self.settings.featherless_api_key,
                                       timeout=self.settings.llm_timeout_s,
                                       max_retries=2)
        return self._client

    async def chat(self, model: str, messages: list[dict[str, Any]],
                   json_mode: bool = False, temperature: float = 0.0,
                   max_tokens: int = 2000) -> str:
        client = self._get()
        kwargs: dict[str, Any] = {"model": model, "messages": messages,
                                  "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        async with self._sem:
            resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    async def chat_json(self, model: str, messages: list[dict[str, Any]],
                        **kwargs) -> dict:
        text = await self.chat(model, messages, json_mode=True, **kwargs)
        return parse_json_object(text)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
