"""Environment-based configuration. Secrets live in env vars — never in code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _req(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name} (see .env.example)")
    return val


@dataclass(frozen=True)
class Settings:
    featherless_api_key: str
    featherless_base_url: str
    agentboxd_api_key: str
    agentboxd_webhook_secret: str
    model_triage: str      # fast/cheap — pick in the Featherless playground
    model_forensic: str    # long-context
    model_vision: str      # open vision model, Qwen-VL-class
    model_redteam: str     # long-context, creative
    graph_path: str = "data/threat_graph.json"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings(
            featherless_api_key=_req("FEATHERLESS_API_KEY"),
            featherless_base_url=os.environ.get(
                "FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"
            ),
            agentboxd_api_key=_req("AGENTBOXD_API_KEY"),
            agentboxd_webhook_secret=_req("AGENTBOXD_WEBHOOK_SECRET"),
            model_triage=_req("MODEL_TRIAGE"),
            model_forensic=os.environ.get("MODEL_FORENSIC", "moonshotai/Kimi-K3"),
            model_vision=_req("MODEL_VISION"),
            model_redteam=os.environ.get("MODEL_REDTEAM", "moonshotai/Kimi-K3"),
        )
    return _settings


def reset_settings() -> None:  # for tests
    global _settings
    _settings = None
