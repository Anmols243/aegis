"""Thin wrapper over Featherless's OpenAI-compatible API."""
from __future__ import annotations

import json
from openai import OpenAI

from .config import get_settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = OpenAI(base_url=s.featherless_base_url, api_key=s.featherless_api_key)
    return _client


def chat(model: str, messages: list[dict], **kwargs) -> str:
    """Plain chat completion. Returns the assistant's text (never None)."""
    resp = get_client().chat.completions.create(model=model, messages=messages, **kwargs)
    return resp.choices[0].message.content or ""


def chat_json(model: str, messages: list[dict], temperature: float = 0.0,
              **kwargs) -> dict:
    """Chat completion forced into a JSON object. Raises on invalid JSON."""
    text = chat(
        model,
        messages,
        response_format={"type": "json_object"},
        temperature=temperature,
        **kwargs,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON: {text[:500]}") from e
