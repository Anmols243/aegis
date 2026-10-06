"""Environment-based configuration.

LLM auth (Featherless) is NOT here — the key lives in the Secure Vault and
src/aegis/llm.py reaches it through the featherless skill CLI. AgentBoxD
secrets are read on demand, so the pure-LLM paths (triage, forensic, …)
run without them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _req(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name} (see .env.example)")
    return val


def agentboxd_api_key() -> str:
    return _req("AGENTBOXD_API_KEY")


def agentboxd_webhook_secret() -> str:
    return _req("AGENTBOXD_WEBHOOK_SECRET")


@dataclass(frozen=True)
class Settings:
    # Model IDs verified against the Featherless catalog (override via env).
    model_triage: str = os.environ.get("MODEL_TRIAGE",
                                       "moonshotai/Kimi-K3")
    model_forensic: str = os.environ.get("MODEL_FORENSIC",
                                         "moonshotai/Kimi-K3")
    model_vision: str = os.environ.get("MODEL_VISION",
                                       "Qwen/Qwen3-VL-30B-A3B-Instruct")
    model_redteam: str = os.environ.get("MODEL_REDTEAM",
                                        "moonshotai/Kimi-K3")
    graph_path: str = os.environ.get("GRAPH_PATH", "data/threat_graph.json")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:  # for tests
    global _settings
    _settings = None
