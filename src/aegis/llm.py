"""LLM calls for AEGIS — routed through the featherless skill CLI.

The Featherless API key lives in the Secure Vault (connector
custom.featherless) and is never in env vars, files, or chat. The skill CLI
attaches it via the authd surrogate exchange on every request.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

CHAT_CLI = os.path.expanduser("~/workspace/skills/featherless/bin/chat.py")


_MAX_ATTEMPTS = 3


def _run(model: str, messages: list[dict], as_json: bool = False,
         temperature: float = 0.0, timeout: int = 300) -> dict:
    """Full chat-completions response dict via the skill CLI.

    Retries transient failures with exponential backoff (2s, 8s) so a
    flaky provider doesn't kill an analysis outright.
    """
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
