"""End-to-end API tests: real app, real queue, fake LLM, stubbed network."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from aegis.core import config as config_mod

from .conftest import wait_done


def submit(client, **body):
    r = client.post("/api/v1/analyses", json=body)
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_health(client):
    h = client.get("/api/v1/health").json()
    assert h["ok"] and h["llm"] is True


def test_scam_sample_end_to_end(client):
    aid = submit(client, sample_id="paypal-phish")
    a = wait_done(client, aid)
    assert a["status"] == "done"
    assert a["label"] == "SCAM"
    assert [s["status"] for s in a["stages"]] == [
        "done", "done", "done", "done", "skipped", "done", "done", "done", "done"]
    # the fabricated quote from the fake model was dropped by the grounding check
    assert all("wire the money" not in f["excerpt"] for f in a["findings"])
    assert a["findings"] and a["red_flags"] and a["actions"]
    assert a["email"]["subject"].startswith("Action required")


def test_legit_mail_is_cleared(client):
    a = wait_done(client, submit(client, sample_id="legit-personal"))
    assert a["label"] == "LIKELY_SAFE"


def test_pasted_raw_and_file_upload(client):
    a = wait_done(client, submit(client, raw="hello, lunch tomorrow at noon? cheers"))
    assert a["status"] == "done" and a["source"] == "web"
    files = {"file": ("mail.eml", b"From: x@y.example\nSubject: hi\n\nsee you soon friend",
                      "message/rfc822")}
    r = client.post("/api/v1/analyses", files=files)
    assert r.status_code == 202
    assert wait_done(client, r.json()["id"])["email"]["subject"] == "hi"


def test_validation_errors(client):
    assert client.post("/api/v1/analyses", json={"raw": "hi"}).status_code == 422
    assert client.post("/api/v1/analyses", json={"sample_id": "nope"}).status_code == 404
    assert client.post("/api/v1/analyses", json={"raw": 5}).status_code == 422
    assert client.get("/api/v1/analyses/a_missing").status_code == 404


def test_sse_replays_and_finishes(client):
    aid = submit(client, sample_id="parcel-fee")
    wait_done(client, aid)
    with client.stream("GET", f"/api/v1/analyses/{aid}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert "event: stage" in body and "event: done" in body
    done = json.loads(body.split("event: done\ndata: ")[1].split("\n")[0])
    assert done["status"] == "done"


def test_list_filter_and_cursor(client):
    for sid in ("paypal-phish", "legit-personal", "legit-receipt"):
        wait_done(client, submit(client, sample_id=sid))
    page = client.get("/api/v1/analyses?limit=2").json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = client.get(f"/api/v1/analyses?limit=2&cursor={page['next_cursor']}").json()
    assert len(rest["items"]) == 1
    safe = client.get("/api/v1/analyses?label=LIKELY_SAFE").json()["items"]
    assert {i["label"] for i in safe} == {"LIKELY_SAFE"}


def test_share_link_is_redacted(client):
    a = wait_done(client, submit(client, sample_id="paypal-phish"))
    shared = client.get(f"/api/v1/share/{a['share_token']}").json()
    assert shared["label"] == "SCAM"
    assert "text" not in shared["email"] and shared["triage"] is None
    assert shared["share_token"] is None and shared["card_markdown"] == ""
    assert client.get("/api/v1/share/s_unknown").status_code == 404


def test_abuse_report(client):
    a = wait_done(client, submit(client, sample_id="paypal-phish"))
    md = client.get(f"/api/v1/analyses/{a['id']}/abuse-report").json()["markdown"]
    assert "paypa1-secure.com" in md and "abuse@" in md


def test_campaign_links_repeat_infrastructure(client):
    a1 = wait_done(client, submit(client, sample_id="paypal-phish"))
    a2 = wait_done(client, submit(client, sample_id="paypal-phish"))
    assert a2["campaign"]["related"] and a2["campaign"]["campaign_id"]
    camps = client.get("/api/v1/campaigns").json()
    ids = {x["id"] for c in camps["campaigns"] for x in c["analyses"]}
    assert {a1["id"], a2["id"]} <= ids
    assert camps["graph"]["nodes"] and camps["graph"]["links"]


def test_redteam_run(client):
    r = client.post("/api/v1/redteam/runs", json={"sample_id": "paypal-phish", "n": 3, "seed": 5})
    assert r.status_code == 202
    rid = r.json()["id"]
    run = client.get(f"/api/v1/redteam/runs/{rid}").json()
    for v in run["variants"]:
        wait_done(client, v["analysis_id"])
    run = client.get(f"/api/v1/redteam/runs/{rid}").json()
    assert run["status"] == "done" and run["summary"]["total"] == 3
    assert run["summary"]["caught"] + run["summary"]["missed"] == 3
    # red-team variants stay out of the main feed
    feed = client.get("/api/v1/analyses").json()["items"]
    assert all(i["source"] != "redteam" for i in feed)
    assert client.get("/api/v1/redteam/summary").json()["variants"] == 3


def test_stats(client):
    wait_done(client, submit(client, sample_id="paypal-phish"))
    s = client.get("/api/v1/stats").json()
    assert s["total"] == 1 and s["by_label"]["SCAM"] == 1


# --------------------------------------------------------------------------- security

def test_no_cors_headers_by_default(client):
    r = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    assert r.headers["x-frame-options"] == "DENY"


def test_body_limit_enforced(client):
    big = "a" * (3 * 1024 * 1024)
    r = client.post("/api/v1/analyses", content=json.dumps({"raw": big}),
                    headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_api_key_required_when_configured(settings_env, fake_llm, no_network):
    from fastapi.testclient import TestClient

    from aegis.main import create_app
    settings_env.setenv("AEGIS_API_KEY", "s3cret-key")
    config_mod.get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/v1/analyses").status_code == 401
        assert c.get("/api/v1/analyses?token=s3cret-key").status_code == 401  # never via URL
        assert c.get("/api/v1/analyses",
                     headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get("/api/v1/analyses",
                     headers={"Authorization": "Bearer s3cret-key"}).status_code == 200
        assert c.get("/api/v1/health").status_code == 200   # public


def test_submit_rate_limited(client):
    codes = [client.post("/api/v1/analyses", json={"raw": "hello friend, see you at noon"})
             .status_code for _ in range(14)]
    assert 429 in codes


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_signature_and_idempotency(settings_env, fake_llm, no_network):
    from fastapi.testclient import TestClient

    from aegis.main import create_app
    settings_env.setenv("AGENTBOXD_WEBHOOK_SECRET", "whsec")
    config_mod.get_settings.cache_clear()
    event = {"type": "message.received", "data": {"message": {
        "id": "msg_1", "inbox_id": "inb_1", "subject": "Verify",
        "from": "PayPal <x@paypa1-secure.com>",
        "text": "Verify your identity immediately at http://paypa1-secure.com/v",
        "scores": {"phishing": 0.93}}}}
    body = json.dumps(event).encode()
    with TestClient(create_app()) as c:
        url = "/api/v1/ingest/agentboxd"
        assert c.post(url, content=body).status_code == 401
        assert c.post(url, content=body,
                      headers={"X-Mailroom-Signature": "0" * 64}).status_code == 401
        ok = c.post(url, content=body, headers={"X-Mailroom-Signature": _sign(body, "whsec")})
        assert ok.status_code == 202
        dup = c.post(url, content=body, headers={"X-Mailroom-Signature": _sign(body, "whsec")})
        assert dup.status_code == 200 and dup.json()["duplicate"] is True
        a = wait_done(c, ok.json()["id"])
        assert a["source"] == "webhook" and a["label"] == "SCAM"
        assert a["verdict"]["contributions"].get("agentboxd") is not None


@pytest.mark.parametrize("public", [False, True])
def test_inbox_live_feed(settings_env, fake_llm, no_network, public):
    from fastapi.testclient import TestClient

    from aegis.main import create_app
    for k, v in {"AGENTBOXD_WEBHOOK_SECRET": "whsec", "AGENTBOXD_API_KEY": "k",
                 "AGENTBOXD_INBOX_ID": "inb_1", "AGENTBOXD_INBOX_ADDRESS": "test@inbox.example",
                 "AGENTBOXD_AUTO_REPLY": "false", "INBOX_PUBLIC": str(public).lower()}.items():
        settings_env.setenv(k, v)
    config_mod.get_settings.cache_clear()
    event = {"type": "message.received", "data": {"message": {
        "id": "msg_live", "inbox_id": "inb_1", "subject": "Verify",
        "from": "Shabeeh Khan <shabeeh.k@gmail.com>",
        "text": ("Verify your identity immediately at http://paypa1-secure.com/v or call "
                 "+1 800-555-0142. Reply to shabeeh.k@gmail.com.")}}}
    body = json.dumps(event).encode()
    with TestClient(create_app()) as c:
        ok = c.post("/api/v1/ingest/agentboxd", content=body,
                    headers={"X-Mailroom-Signature": _sign(body, "whsec")})
        wait_done(c, ok.json()["id"])
        live = c.get("/api/v1/inbox/live").json()
        detail = c.get(f"/api/v1/inbox/live/{live['items'][0]['key']}").json()
        assert c.get("/api/v1/inbox/live/0123456789ab").status_code == 404
        assert c.get("/api/v1/inbox/live/not-a-key").status_code == 404
    assert live["enabled"] is True and live["address"] == "test@inbox.example"
    [item] = live["items"]
    assert item["status"] == "done" and item["label"] and item["stages"] and item["key"]
    # a test inbox: subject, masked sender and a censored preview are always shown
    assert item["subject"] == "Verify" and item["sender"] == "sh***@gmail.com"
    assert "paypa1-secure.com" in item["preview"]           # evidence stays
    assert "0142" not in item["preview"] and "***42" in item["preview"]
    assert "shabeeh.k@" not in item["preview"]
    # the id (opens the uncensored case) only for public inbox mail
    assert item["id"] == (ok.json()["id"] if public else None)
    assert item["private"] is (not public)
    # the dissection works either way and is censored
    assert detail["status"] == "done" and detail["label"] and detail["stages"]
    assert detail["id"] is None and detail["share_token"] is None
    dumped = json.dumps(detail)
    assert "shabeeh.k@gmail.com" not in dumped and "Shabeeh Khan" not in dumped
    assert "555-0142" not in dumped and "paypa1-secure.com" in dumped


def test_inbox_live_disabled_without_agentboxd(client):
    assert client.get("/api/v1/inbox/live").json() == {
        "enabled": False, "address": None, "public": False, "items": []}


def test_webhook_disabled_without_secret(client):
    assert client.post("/api/v1/ingest/agentboxd", content=b"{}").status_code == 503


def test_body_limit_enforced_while_streaming(client):
    """A chunked upload has no Content-Length; the limit must trip mid-stream."""
    def chunks():
        for _ in range(64):
            yield b"x" * 65536            # 4 MB total, no length header
    r = client.post("/api/v1/analyses", content=chunks(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 413
