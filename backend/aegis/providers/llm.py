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


# `\'` is not a JSON escape, but models write it (`PayPal\'s`); a preceding backslash pair
# is a literal backslash and is left alone
_BAD_APOSTROPHE = re.compile(r"(?<!\\)((?:\\\\)*)\\'")


def _loads(t: str):
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return json.loads(_BAD_APOSTROPHE.sub(lambda m: m.group(1) + "'", t))


def parse_json_object(text: str) -> dict:
    """Pull one JSON object out of a model reply. Raises LLMBadOutput."""
    t = _FENCE.sub("", (text or "").strip())
    try:
        data = _loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            raise LLMBadOutput(f"no JSON object in model output: {t[:200]!r}") from None
        try:
            data = _loads(t[start:end + 1])
        except json.JSONDecodeError as e:
            raise LLMBadOutput(f"invalid JSON in model output: {t[:200]!r}") from e
    if not isinstance(data, dict):
        raise LLMBadOutput("model output is not a JSON object")
    return data


def _completion_choice(response):
    """Validate the provider envelope before indexing it.

    Missing or null choices are bad output, rather than an indexing error,
    so stage recovery can retry them.
    """
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices or choices[0] is None:
        raise LLMBadOutput("provider returned no completion choices")
    return choices[0]


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
                   max_tokens: int = 2000, response_schema: dict | None = None) -> str:
        client = self._get()
        kwargs: dict[str, Any] = {"model": model, "messages": messages,
                                  "temperature": temperature, "max_tokens": max_tokens}
        if response_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema", "json_schema": {
                    "name": "aegis_report", "strict": True, "schema": response_schema}}
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        async with self._sem:
            resp = await client.chat.completions.create(**kwargs)
            choice = _completion_choice(resp)
            if choice.finish_reason == "length":
                # cut off by max_tokens (a reasoning model can spend most of it thinking):
                # half an answer is useless, so try once more with double the budget
                kwargs["max_tokens"] = max_tokens * 2
                resp = await client.chat.completions.create(**kwargs)
                choice = _completion_choice(resp)
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMBadOutput("provider returned no completion text")
        return content

    async def chat_json(self, model: str, messages: list[dict[str, Any]],
                        **kwargs) -> dict:
        text = await self.chat(model, messages, json_mode=True, **kwargs)
        return parse_json_object(text)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
