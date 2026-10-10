"""End-to-end API tests: real app, real queue, fake LLM, stubbed network."""
from __future__ import annotations

import hashlib
import hmac
import json
import re

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


VIEWER_A = {"X-Aegis-Viewer": "viewer-a-" + "a" * 40}
VIEWER_B = {"X-Aegis-Viewer": "viewer-b-" + "b" * 40}


def _inbox_app(settings_env):
    from aegis.main import create_app
    for k, v in {"AGENTBOXD_WEBHOOK_SECRET": "whsec", "AGENTBOXD_API_KEY": "k",
                 "AGENTBOXD_INBOX_ID": "inb_1", "AGENTBOXD_INBOX_ADDRESS": "test@inbox.example",
                 "AGENTBOXD_AUTO_REPLY": "false"}.items():
        settings_env.setenv(k, v)
    config_mod.get_settings.cache_clear()
    return create_app()


def _deliver(c, mid: str, subject: str, sender: str = "Shabeeh Khan <shabeeh.k@gmail.com>") -> str:
    event = {"type": "message.received", "data": {"message": {
        "id": mid, "inbox_id": "inb_1", "subject": subject,
        "from": sender,
        "text": ("Verify your identity immediately at http://paypa1-secure.com/v or call "
                 "+1 800-555-0142. Reply to shabeeh.k@gmail.com.")}}}
    body = json.dumps(event).encode()
    ok = c.post("/api/v1/ingest/agentboxd", content=body,
                headers={"X-Mailroom-Signature": _sign(body, "whsec")})
    wait_done(c, ok.json()["id"])
    return ok.json()["id"]


def test_inbox_live_feed_is_per_browser(settings_env, fake_llm, no_network):
    from fastapi.testclient import TestClient
    with TestClient(_inbox_app(settings_env)) as c:
        code = c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["code"]
        assert re.fullmatch(r"AEGIS-[A-Z2-9]{6}", code)
        # stable per browser, different across browsers, none without a browser
        assert c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["code"] == code
        assert c.get("/api/v1/inbox/live", headers=VIEWER_B).json()["code"] != code
        assert c.get("/api/v1/inbox/live").json()["code"] is None
        mine = _deliver(c, "msg_a", f"Verify [{code.lower()}]")   # case-insensitive
        _deliver(c, "msg_none", "Verify", "Someone <other@example.com>")   # no code: nobody's
        live = c.get("/api/v1/inbox/live", headers=VIEWER_A).json()
        detail = c.get(f"/api/v1/inbox/live/{live['items'][0]['key']}", headers=VIEWER_A).json()
        other = c.get("/api/v1/inbox/live", headers=VIEWER_B).json()
        other_detail = c.get(f"/api/v1/inbox/live/{live['items'][0]['key']}", headers=VIEWER_B)
        anon = c.get("/api/v1/inbox/live").json()
        cases_a = c.get("/api/v1/analyses", headers=VIEWER_A).json()["items"]
        cases_b = c.get("/api/v1/analyses", headers=VIEWER_B).json()["items"]
        assert c.get("/api/v1/inbox/live/0123456789ab", headers=VIEWER_A).status_code == 404
        assert c.get("/api/v1/inbox/live/not-a-key", headers=VIEWER_A).status_code == 404
    assert live["enabled"] is True and live["address"] == "test@inbox.example"
    [item] = live["items"]                     # only the mail that carried A's code
    assert item["id"] == mine and item["status"] == "done" and item["stages"]
    assert item["subject"] == "Verify"                     # the routing code is not shown
    assert item["sender"] == "sh***@gmail.com"
    assert "paypa1-secure.com" in item["preview"]           # evidence stays
    assert "0142" not in item["preview"] and "***42" in item["preview"]
    assert "shabeeh.k@" not in item["preview"]
    assert detail["status"] == "done" and detail["id"] == mine and detail["share_token"] is None
    dumped = json.dumps(detail)
    assert "shabeeh.k@gmail.com" not in dumped and "555-0142" not in dumped
    # another browser, or none, sees nothing of it
    assert other["items"] == [] and anon["items"] == [] and other_detail.status_code == 404
    assert mine in [a["id"] for a in cases_a]
    assert all(a["source"] == "sample" for a in cases_b)


def test_sender_linked_by_a_coded_email(settings_env, fake_llm, no_network):
    """After one coded email, mail from the same address needs no code; a wipe forgets it."""
    from fastapi.testclient import TestClient
    with TestClient(_inbox_app(settings_env)) as c:
        code = c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["code"]
        before = _deliver(c, "msg_0", "Hello", "Me <ME@Example.com>")    # not linked yet
        coded = _deliver(c, "msg_1", f"Hello {code}", "Me <me@example.com>")
        later = _deliver(c, "msg_2", "Plain subject", "Other Name <me@example.COM>")
        stranger = _deliver(c, "msg_3", "Plain subject", "x <stranger@example.com>")
        ids = {i["id"] for i in c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["items"]}
        assert ids == {coded, later} and before not in ids and stranger not in ids
        c.delete("/api/v1/history", headers=VIEWER_A)
        after = _deliver(c, "msg_4", "Plain subject", "Me <me@example.com>")
        assert c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["items"] == []
        assert c.get(f"/api/v1/analyses/{after}").status_code == 200   # exists, owned by nobody


def test_startup_unpublishes_inbox_mail(settings_env, fake_llm, no_network, tmp_path):
    """Inbox mail left public from an INBOX_PUBLIC period goes private on the next start."""
    import sqlite3

    from fastapi.testclient import TestClient

    from aegis.main import create_app
    with TestClient(create_app()) as c:
        ids = [c.post("/api/v1/analyses", json={"raw": f"Subject: t{i}\n\nHello there, friend."}).json()["id"]
               for i in range(2)]
    db = sqlite3.connect(tmp_path / "t.db")
    db.execute("UPDATE analyses SET source = 'poller', visibility = 'public' WHERE id = ?", (ids[0],))
    db.execute("UPDATE analyses SET source = 'sample', visibility = 'public' WHERE id = ?", (ids[1],))
    db.commit()
    with TestClient(create_app()):
        pass
    vis = dict(db.execute("SELECT id, visibility FROM analyses").fetchall())
    db.close()
    assert vis[ids[0]] == "private" and vis[ids[1]] == "public"


def test_delete_history_erases_only_own(settings_env, fake_llm, no_network):
    from fastapi.testclient import TestClient
    with TestClient(_inbox_app(settings_env)) as c:
        code = c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["code"]
        emailed = _deliver(c, "msg_a", f"Verify {code}")
        pasted = c.post("/api/v1/analyses", json={"raw": "Subject: hi\n\nSee you at lunch."},
                        headers=VIEWER_A).json()["id"]
        kept = c.post("/api/v1/analyses", json={"raw": "Subject: yo\n\nSee you at dinner."},
                      headers=VIEWER_B).json()["id"]
        wait_done(c, pasted)
        wait_done(c, kept)
        assert c.delete("/api/v1/history").status_code == 403      # needs a browser
        assert c.delete("/api/v1/history", headers=VIEWER_A).json() == {"deleted": 2}
        assert c.get(f"/api/v1/analyses/{emailed}").status_code == 404
        assert c.get(f"/api/v1/analyses/{pasted}").status_code == 404
        assert c.get(f"/api/v1/analyses/{kept}").status_code == 200
        assert c.get("/api/v1/inbox/live", headers=VIEWER_A).json()["items"] == []
        assert c.get("/api/v1/analyses?mine=true", headers=VIEWER_A).json()["items"] == []


def test_inbox_live_disabled_without_agentboxd(client):
    assert client.get("/api/v1/inbox/live").json() == {
        "enabled": False, "address": None, "public": False, "code": None, "items": []}


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
