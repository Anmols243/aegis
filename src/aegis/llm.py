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

CHAT_CLI = os.path.expanduser("~/workspace/skills/featherless/bin/chat.py")


def _run(model: str, messages: list[dict], as_json: bool = False,
         temperature: float = 0.0, timeout: int = 300) -> dict:
    """Full chat-completions response dict via the skill CLI."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(messages, f)
        path = f.name
    try:
        cmd = [CHAT_CLI, "--model", model, "--messages-file", path,
               "--temperature", str(temperature), "--raw"]
        if as_json:
            cmd.append("--json")
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"featherless skill failed: {proc.stderr.strip()[:300]}")
        return json.loads(proc.stdout)
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
