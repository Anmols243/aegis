"""Offline test suite — everything here runs WITHOUT API keys.

Live-LLM paths (triage, forensic, mutate, vision inspect, full pipeline)
are exercised by scripts/smoke_llm.py once keys are set.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegis.agents.arbiter import Label, arbitrate
from aegis.agents.sandbox import PageKind, SandboxVerdict, is_blocked_ip, url_allowed
from aegis.graph.store import EmailEntities, ThreatGraph
from aegis.verdict import DEFAULT_ACTION_PLANS, RedFlag, VerdictCard, render


class TestArbiter(unittest.TestCase):
    def test_scam_threshold(self):
        v = arbitrate({"agentboxd_phishing": 0.9, "forensic": 0.85,
                       "vision": None, "sandbox": 1.0})
        self.assertEqual(v.label, Label.SCAM)
        self.assertGreaterEqual(v.confidence, 0.3)

    def test_suspicious_band(self):
        v = arbitrate({"agentboxd_phishing": 0.5, "forensic": 0.5,
                       "vision": None, "sandbox": None})
        self.assertEqual(v.label, Label.SUSPICIOUS)

    def test_likely_safe(self):
        v = arbitrate({"agentboxd_phishing": 0.05, "forensic": 0.1,
                       "vision": 0.0, "sandbox": 0.1})
        self.assertEqual(v.label, Label.LIKELY_SAFE)

    def test_fail_closed_without_forensic(self):
        # Clean signals everywhere else, but no forensic → never LIKELY_SAFE.
        v = arbitrate({"agentboxd_phishing": 0.05, "forensic": None,
                       "vision": 0.0, "sandbox": 0.1})
        self.assertNotEqual(v.label, Label.LIKELY_SAFE)

    def test_no_signals_fails_closed(self):
        v = arbitrate({"agentboxd_phishing": None, "forensic": None,
                       "vision": None, "sandbox": None})
        self.assertEqual(v.label, Label.SUSPICIOUS)

    def test_dissent_noted(self):
        v = arbitrate({"agentboxd_phishing": 0.0, "forensic": 0.1,
                       "vision": 1.0, "sandbox": 0.1})
        self.assertTrue(v.dissent, "expected dissent when agents disagree")

    def test_weights_renormalize(self):
        # Only one signal present → it decides alone.
        v = arbitrate({"agentboxd_phishing": None, "forensic": 0.95,
                       "vision": None, "sandbox": None})
        self.assertEqual(v.label, Label.SCAM)


class TestThreatGraph(unittest.TestCase):
    def test_campaign_clustering(self):
        path = tempfile.mktemp(suffix=".json")
        g = ThreatGraph(path)
        g.add_email(EmailEntities("e1", senders=["a@evil.com"],
                                  domains=["paypa1-secure.com"],
                                  urls=["http://paypa1-secure.com/verify"],
                                  body="verify your account now click URL"))
        g.add_email(EmailEntities("e2", senders=["b@evil.com"],
                                  domains=["paypa1-secure.com"],
                                  urls=["http://paypa1-secure.com/login"],
                                  body="verify your account now click URL"))
        g.add_email(EmailEntities("e3", senders=["c@nice.com"],
                                  domains=["example.com"], body="hello world"))
        camps = g.campaigns()
        self.assertEqual(len(camps), 1)
        camp = g.campaign_for("e1")
        self.assertIsNotNone(camp)
        self.assertIsNone(g.campaign_for("e3"))
        # persistence round-trip
        g2 = ThreatGraph(path)
        self.assertEqual(len(g2.campaigns()), 1)


class TestVerdictCard(unittest.TestCase):
    def test_render(self):
        v = arbitrate({"agentboxd_phishing": 0.9, "forensic": 0.9,
                       "vision": None, "sandbox": 1.0})
        card = render(VerdictCard(
            v, [RedFlag("Lookalike domain", "paypa1-secure.com")],
            DEFAULT_ACTION_PLANS[v.label], "Linked to campaign #1"))
        self.assertIn("SCAM", card)
        self.assertIn("paypa1-secure.com", card)
        self.assertIn("What to do next", card)


class TestSandboxGuards(unittest.TestCase):
    def test_blocked_ips(self):
        for ip in ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254",
                   "::1", "not-an-ip"]:
            self.assertTrue(is_blocked_ip(ip), ip)
        self.assertFalse(is_blocked_ip("8.8.8.8"))
        self.assertFalse(is_blocked_ip("1.1.1.1"))

    def test_url_allowed_literal_ips(self):
        ok, _ = url_allowed("http://127.0.0.1/evil")
        self.assertFalse(ok)
        ok, _ = url_allowed("http://10.1.2.3:8080/x")
        self.assertFalse(ok)

    def test_url_allowed_schemes(self):
        for u in ["javascript:alert(1)", "ftp://x.com/f", "file:///etc/passwd"]:
            ok, _ = url_allowed(u)
            self.assertFalse(ok, u)

    def test_sandbox_verdict_risk_mapping(self):
        self.assertEqual(
            SandboxVerdict(url="u", kind=PageKind.CREDENTIAL_HARVEST).risk, 1.0)
        self.assertEqual(
            SandboxVerdict(url="u", kind=PageKind.BENIGN).risk, 0.1)


class TestWebhookHmac(unittest.TestCase):
    def test_signature_rejection(self):
        os.environ.update({
            "FEATHERLESS_API_KEY": "dummy", "AGENTBOXD_API_KEY": "dummy",
            "AGENTBOXD_WEBHOOK_SECRET": "testsecret",
            "MODEL_TRIAGE": "dummy", "MODEL_VISION": "dummy",
        })
        from fastapi.testclient import TestClient
        from aegis.ingress.webhook import app

        client = TestClient(app)
        body = json.dumps({"data": {"message": {"id": "m1"}}}).encode()
        # bad signature → 401
        r = client.post("/webhook/agentboxd", content=body,
                        headers={"X-Mailroom-Signature": "wrong"})
        self.assertEqual(r.status_code, 401)
        # good signature → 202-style ok (background task errors are contained)
        sig = hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
        r = client.post("/webhook/agentboxd", content=body,
                        headers={"X-Mailroom-Signature": sig})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(client.get("/health").json()["ok"], True)


class TestVisionRender(unittest.TestCase):
    def test_static_render(self):
        try:
            from aegis.agents.vision_inspector import render_html
            path = render_html("<html><body><h1>hi</h1></body></html>")
        except Exception as e:
            self.skipTest(f"chromium unavailable: {e}")
            return
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
