"""Test fixtures. The LLM is replaced with a deterministic fake, the sandbox
network is stubbed for API tests, and every test gets a fresh database."""
from __future__ import annotations

import json
import re
import time

import pytest

from aegis.core import config as config_mod
from aegis.pipeline import sandbox
from aegis.providers import llm as llm_mod


def fake_reply(model: str, messages: list[dict]) -> dict:
    system = messages[0]["content"] if isinstance(messages[0]["content"], str) else ""
    user = messages[-1]["content"]
    text = user if isinstance(user, str) else ""
    m = re.search(r"<UNTRUSTED_EMAIL>(.*)</UNTRUSTED_EMAIL>", text, re.DOTALL)
    text = m.group(1) if m else text   # judge the email body only, like a real analyst
    if "AEGIS-Triage" in system:
        return {"urls": re.findall(r"https?://[^\s<>\"']+", text), "phone_numbers": [],
                "urgency_signals": ["within 24 hours"] if "24 hours" in text else [],
                "requested_action": "verify account", "language": "en",
                "brand_mentions": ["PayPal"] if "PayPal" in text else []}
    if "AEGIS-Forensic" in system:
        scam = any(w in text.lower() for w in ("verify", "gift card", "suspension"))
        quote = "verify your identity immediately" if "verify your identity" in text else "zzz"
        return {"findings": [
                    {"claim": "Urgent identity verification demand", "severity": "high",
                     "evidence": {"artifact": "body", "excerpt": quote}},
                    {"claim": "Invented quote that is not in the email", "severity": "high",
                     "evidence": {"artifact": "body", "excerpt": "wire the money to Bob"}}],
                "deception_techniques": ["urgency-pressure"] if scam else [],
                "risk_score": 0.95 if scam else 0.05,
                "summary": "Looks like phishing." if scam else "Looks ordinary."}
    return {"impersonated_brand": None, "confidence": 0.0, "notable_regions": [], "reason": ""}


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 't.db').as_posix()}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")
    monkeypatch.setenv("VISION_ENABLED", "false")
    for k in ("AEGIS_API_KEY", "AGENTBOXD_API_KEY", "AGENTBOXD_WEBHOOK_SECRET",
              "AGENTBOXD_INBOX_ID", "CORS_ORIGINS"):
        monkeypatch.delenv(k, raising=False)
    config_mod.get_settings.cache_clear()
    yield monkeypatch
    config_mod.get_settings.cache_clear()


@pytest.fixture
def fake_llm(monkeypatch):
    async def chat_json(self, model, messages, **kw):
        return fake_reply(model, messages)
    monkeypatch.setattr(llm_mod.LLMClient, "chat_json", chat_json)


@pytest.fixture
def no_network(monkeypatch):
    async def inspect(url):
        return sandbox.LinkVerdict(url=url, final_url=url, kind="unreachable",
                                   failure_reason="stubbed in tests")
    monkeypatch.setattr(sandbox, "inspect_url", inspect)


@pytest.fixture
def client(settings_env, fake_llm, no_network):
    from fastapi.testclient import TestClient

    from aegis.main import create_app
    with TestClient(create_app()) as c:
        yield c


def wait_done(client, analysis_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        a = client.get(f"/api/v1/analyses/{analysis_id}").json()
        if a["status"] in ("done", "failed"):
            return a
        time.sleep(0.1)
    raise AssertionError(f"analysis {analysis_id} did not finish: {json.dumps(a)[:300]}")
