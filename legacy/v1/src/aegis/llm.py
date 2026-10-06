"""LLM calls for AEGIS — routed through the featherless skill CLI.

The Featherless API key lives in the Secure Vault (connector
custom.featherless) and is never in env vars, files, or chat. The skill CLI
attaches it via the authd surrogate exchange on every request.

Where that CLI isn't installed, FEATHERLESS_API_KEY (if set) is used to call
the OpenAI-compatible Featherless API directly. With neither, calls fail
fast and the orchestrator's fail-closed fallbacks take over.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

CHAT_CLI = os.path.expanduser("~/workspace/skills/featherless/bin/chat.py")


FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

_MAX_ATTEMPTS = 3


def _run_api(model: str, messages: list[dict], as_json: bool,
             temperature: float, timeout: int) -> dict:
    """Same response dict, via the Featherless API with FEATHERLESS_API_KEY."""
    from openai import OpenAI

    client = OpenAI(base_url=FEATHERLESS_BASE_URL,
                    api_key=os.environ["FEATHERLESS_API_KEY"],
                    timeout=timeout, max_retries=_MAX_ATTEMPTS - 1)
    kwargs: dict = {"model": model, "messages": messages,
                    "temperature": temperature}
    if as_json:
        kwargs["response_format"] = {"type": "json_object"}
    return client.chat.completions.create(**kwargs).model_dump()


def _run(model: str, messages: list[dict], as_json: bool = False,
         temperature: float = 0.0, timeout: int = 300) -> dict:
    """Full chat-completions response dict via the skill CLI.

    Retries transient failures with exponential backoff (2s, 8s) so a
    flaky provider doesn't kill an analysis outright.
    """
    if not os.path.exists(CHAT_CLI):
        if os.environ.get("FEATHERLESS_API_KEY"):
            return _run_api(model, messages, as_json, temperature, timeout)
        raise RuntimeError("no LLM backend: featherless skill CLI not found "
                           "and FEATHERLESS_API_KEY is not set")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(messages, f)
        path = f.name
    try:
        cmd = [CHAT_CLI, "--model", model, "--messages-file", path,
               "--temperature", str(temperature), "--raw"]
        if as_json:
            cmd.append("--json")
        last_err: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=timeout)
            except subprocess.TimeoutExpired as e:
                last_err = e
            else:
                if proc.returncode == 0:
                    return json.loads(proc.stdout)
                last_err = RuntimeError(
                    f"featherless skill failed: {proc.stderr.strip()[:300]}")
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(2 ** (attempt + 1))
        raise last_err  # type: ignore[misc]
    finally:
        os.unlink(path)


def chat(model: str, messages: list[dict], **kwargs) -> str:
    """Plain chat completion. Returns the assistant's text (never None)."""
    data = _run(model, messages,
                temperature=kwargs.get("temperature", 0.0))
    return data["choices"][0]["message"]["content"] or ""


def chat_json(model: str, messages: list[dict], temperature: float = 0.0,
              **kwargs) -> dict:
    """Chat completion forced into a JSON object. Raises on invalid JSON."""
    data = _run(model, messages, as_json=True, temperature=temperature)
    text = data["choices"][0]["message"]["content"] or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON: {text[:500]}") from e
