"""Sign in with Google / Microsoft: OAuth state + PKCE, same-browser and
other-browser (pairing code) completion, polling, tagging, token rotation,
revoke on disconnect. Both providers are faked with an httpx MockTransport."""
from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest

from aegis.providers import google, microsoft, oauth
from aegis.services.samples import BY_ID

from .conftest import wait_done

A = {"X-Aegis-Viewer": "viewer-a-" + "a" * 40}
B = {"X-Aegis-Viewer": "viewer-b-" + "b" * 40}
PHISH = BY_ID["paypal-phish"]["raw"]
MS_SCOPE = "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/User.Read"


@pytest.fixture
def oauth_env(settings_env, monkeypatch):
    for p in ("GOOGLE", "MICROSOFT"):
        monkeypatch.setenv(f"{p}_CLIENT_ID", f"{p.lower()}-cid")
        monkeypatch.setenv(f"{p}_CLIENT_SECRET", f"{p.lower()}-secret")


def _pkce_ok(verifier: str, challenge: str | None) -> bool:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()
                                    ).rstrip(b"=").decode() == challenge


@pytest.fixture
def fake(monkeypatch):
    st = {"challenge": None, "pair": None,
          "g_scope": google.SCOPE, "g_messages": {}, "g_history": 500, "g_labels": [],
          "g_modified": [], "revoked": [],
          "ms_scope": MS_SCOPE, "ms_messages": [], "ms_patched": [], "ms_refresh_seen": [],
          "ms_downloads": []}

    def token(req: httpx.Request, ms: bool) -> httpx.Response:
        form = parse_qs(req.content.decode())
        if form["grant_type"] == ["authorization_code"]:
            if form["code"] != ["good-code"] or not _pkce_ok(form["code_verifier"][0],
                                                             st["challenge"]):
                return httpx.Response(400, json={"error": "invalid_grant"})
            if ms:
                return httpx.Response(200, json={"access_token": "ms-at-1", "expires_in": 3599,
                                                 "refresh_token": "rt-ms-1",
                                                 "scope": st["ms_scope"]})
            return httpx.Response(200, json={"access_token": "at-1", "expires_in": 3599,
                                             "refresh_token": "rt-secret-1",
                                             "scope": st["g_scope"]})
        if ms:
            st["ms_refresh_seen"].append(form["refresh_token"][0])
            return httpx.Response(200, json={"access_token": "ms-at-2", "expires_in": 3599,
                                             "refresh_token": "rt-ms-2"})
        return httpx.Response(200, json={"access_token": "at-2", "expires_in": 3599})

    def gmail(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"].startswith("Bearer at-")
        path = req.url.path.removeprefix("/gmail/v1/users/me")
        if path == "/profile":
            return httpx.Response(200, json={"emailAddress": "me@gmail.com",
                                             "historyId": str(st["g_history"])})
        if path == "/history":
            start = int(req.url.params["startHistoryId"])
            recs = [{"id": str(h), "messagesAdded": [{"message": {"id": mid,
                                                                   "labelIds": labels}}]}
                    for mid, (h, labels, _) in st["g_messages"].items() if h > start]
            return httpx.Response(200, json={"history": recs,
                                             "historyId": str(st["g_history"])})
        if path.startswith("/messages/") and path.endswith("/modify"):
            st["g_modified"].append((path.split("/")[2], json.loads(req.content)["addLabelIds"]))
            return httpx.Response(200, json={})
        if path.startswith("/messages/"):
            mid = path.split("/")[2]
            raw = st["g_messages"][mid][2]
            if req.url.params["format"] == "minimal":
                return httpx.Response(200, json={"id": mid, "sizeEstimate": len(raw)})
            return httpx.Response(200, json={"raw": base64.urlsafe_b64encode(raw).decode()})
        if path == "/labels" and req.method == "GET":
            return httpx.Response(200, json={"labels": st["g_labels"]})
        if path == "/labels":
            lb = {"id": f"Label_{len(st['g_labels']) + 1}", **json.loads(req.content)}
            st["g_labels"].append(lb)
            return httpx.Response(200, json=lb)
        return httpx.Response(404)

    def graph(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"].startswith("Bearer ms-at-")
        path = req.url.path.removeprefix("/v1.0/me")
        if path == "":
            return httpx.Response(200, json={"mail": "me@outlook.com",
                                             "userPrincipalName": "me@outlook.com"})
        if path == "/mailFolders/inbox/messages":
            since = req.url.params["$filter"].removeprefix("receivedDateTime ge ")
            cut = datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()
            rows = sorted((m for m in st["ms_messages"] if m["at"] >= cut),
                          key=lambda m: m["at"])
            return httpx.Response(200, json={"value": [
                {"id": m["id"], "isDraft": m["draft"], "receivedDateTime":
                 datetime.fromtimestamp(m["at"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
                for m in rows]})
        if path.endswith("/$value"):
            mid = path.split("/")[2]
            st["ms_downloads"].append(mid)
            return httpx.Response(200, content=next(m["raw"] for m in st["ms_messages"]
                                                    if m["id"] == mid))
        if path.startswith("/messages/") and req.method == "GET":
            return httpx.Response(200, json={"categories": ["Blue category"]})
        if path.startswith("/messages/") and req.method == "PATCH":
            st["ms_patched"].append((path.split("/")[2], json.loads(req.content)))
            return httpx.Response(200, json={})
        return httpx.Response(404)

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url == google.TOKEN_URL:
            return token(req, ms=False)
        if url == microsoft.TOKEN_URL:
            return token(req, ms=True)
        if url == google.REVOKE_URL:
            st["revoked"].append(parse_qs(req.content.decode())["token"][0])
            return httpx.Response(200)
        if req.url.host == "graph.microsoft.com":
            return graph(req)
        return gmail(req)

    monkeypatch.setattr(oauth, "_client",
                        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    oauth._pending.clear()
    oauth._access.clear()
    return st


def start(client, headers, fake, provider="google"):
    r = client.post(f"/api/v1/oauth/{provider}/start", json={"retention_days": 1},
                    headers=headers)
    assert r.status_code == 200, r.text
    q = parse_qs(urlparse(r.json()["url"]).query)
    prov = {"google": google, "microsoft": microsoft}[provider]
    assert q["scope"] == [prov.SCOPE] and q["code_challenge_method"] == ["S256"]
    assert r.json()["url"].startswith(prov.AUTH_URL)
    fake["challenge"] = q["code_challenge"][0]
    fake["pair"] = r.json()["pair"]
    assert r.json()["state"] == q["state"][0]
    return q["state"][0]


def callback(client, headers, provider="google", **params):
    r = client.get(f"/api/v1/oauth/{provider}/callback", params=params, headers=headers,
                   follow_redirects=False)
    assert r.status_code == 303
    return unquote(r.headers["location"])


def status(client, headers, state):
    return client.get("/api/v1/oauth/status", params={"state": state}, headers=headers)


def wait_for(cond, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = cond()
        if v:
            return v
        time.sleep(0.1)
    raise AssertionError("timed out")


# --------------------------------------------------------------------------- general

def test_providers_hidden_when_not_configured(client):
    prov = client.get("/api/v1/mailbox-providers").json()
    assert [p["id"] for p in prov] == ["google", "microsoft"]
    assert not any(p["supported"] for p in prov)
    assert client.post("/api/v1/oauth/google/start", json={}, headers=A).status_code == 503
    assert client.post("/api/v1/oauth/yahoo/start", json={}, headers=A).status_code == 404
    assert client.post("/api/v1/mailboxes", json={}, headers=A).status_code == 405  # no IMAP


def test_state_is_single_use_and_checked(oauth_env, client, fake):
    assert all(p["supported"] for p in client.get("/api/v1/mailbox-providers").json())
    assert client.post("/api/v1/oauth/google/start", json={}).status_code == 403  # no browser
    state = start(client, A, fake)
    assert status(client, A, state).json()["status"] == "pending"
    assert status(client, B, state).status_code == 404                # not B's sign-in
    assert "another provider" in callback(client, A, "microsoft", code="good-code",
                                          state=state)
    state = start(client, A, fake)
    assert callback(client, A, code="good-code", state=state) == "/inbox?signin=connected"
    assert "already used" in callback(client, A, code="good-code", state=state)
    assert "expired" in callback(client, A, code="good-code", state="made-up")
    state = start(client, A, fake)
    assert "cancelled" in callback(client, A, error="access_denied", state=state)
    assert status(client, A, state).json()["status"] == "error"
    state = start(client, A, fake)
    fake["challenge"] = "tampered"                                   # PKCE mismatch
    assert "did not accept" in callback(client, A, code="good-code", state=state)
    assert status(client, A, state).json()["status"] == "error"
    assert len(client.get("/api/v1/mailboxes", headers=A).json()) == 1


def test_missing_mail_permission_is_refused(oauth_env, client, fake):
    fake["g_scope"] = "openid email"
    fake["ms_scope"] = "https://graph.microsoft.com/User.Read"
    for provider in ("google", "microsoft"):
        state = start(client, A, fake, provider)
        assert "permission" in callback(client, A, provider, code="good-code", state=state)
    assert client.get("/api/v1/mailboxes", headers=A).json() == []


def test_other_browser_needs_confirmation(oauth_env, client, fake):
    """AEGIS in an app's built-in browser (A) sends sign-in to the system browser (B)."""
    state = start(client, A, fake)
    loc = callback(client, B, code="good-code", state=state)
    assert loc.startswith("/connect?state=")
    assert client.get("/api/v1/mailboxes", headers=A).json() == []   # nothing until confirmed
    assert client.get("/api/v1/mailboxes", headers=B).json() == []
    st = status(client, A, state).json()
    assert st["status"] == "confirm" and st["email"] == "me@gmail.com"
    pairing = client.get("/api/v1/oauth/pairing", params={"state": state}, headers=B).json()
    assert pairing["pair"] == fake["pair"] and pairing["email"] == "me@gmail.com"
    assert pairing["provider"] == "google"
    assert "rt-secret" not in json.dumps(pairing)
    r = client.post("/api/v1/oauth/confirm", json={"state": state, "connect": True}, headers=B)
    assert r.status_code == 200 and r.json()["status"] == "connected"
    assert [m["email"] for m in client.get("/api/v1/mailboxes", headers=A).json()] == \
        ["me@gmail.com"]                                             # attached to A, the starter
    assert client.get("/api/v1/mailboxes", headers=B).json() == []
    assert status(client, A, state).json()["status"] == "connected"
    r = client.post("/api/v1/oauth/confirm", json={"state": state, "connect": True}, headers=B)
    assert r.status_code == 409                                      # single use


def test_other_browser_can_cancel(oauth_env, client, fake):
    state = start(client, A, fake)
    callback(client, B, code="good-code", state=state)
    r = client.post("/api/v1/oauth/confirm", json={"state": state, "connect": False}, headers=B)
    assert r.json()["status"] == "cancelled"
    assert fake["revoked"] == ["rt-secret-1"]                        # access handed back
    assert client.get("/api/v1/mailboxes", headers=A).json() == []
    assert status(client, A, state).json()["status"] == "cancelled"
    assert client.get("/api/v1/oauth/pairing", params={"state": "nope"}).status_code == 404


# --------------------------------------------------------------------------- Gmail

def test_google_connect_poll_label_revoke(oauth_env, client, fake):
    fake["g_messages"] = {"old": (400, ["INBOX"], b"Subject: old\n\nold")}
    state = start(client, A, fake)
    assert callback(client, A, code="good-code", state=state) == "/inbox?signin=connected"
    mbs = client.get("/api/v1/mailboxes", headers=A).json()
    assert len(mbs) == 1 and mbs[0]["provider"] == "google" and mbs[0]["email"] == "me@gmail.com"
    assert mbs[0]["label_mode"] == "gmail-api" and mbs[0]["retention_days"] == 1
    assert "secret" not in mbs[0] and "rt-secret-1" not in json.dumps(mbs)
    assert client.get("/api/v1/mailboxes", headers=B).json() == []
    mb = mbs[0]
    assert client.post(f"/api/v1/mailboxes/{mb['id']}/pause", headers=B).status_code == 404

    from aegis.db.models import Mailbox
    from aegis.db.session import session_scope

    async def stored_secret():
        async with session_scope() as s:
            return (await s.get(Mailbox, mb["id"])).secret
    assert "rt-secret-1" not in client.portal.call(stored_secret)    # encrypted at rest

    # mail before connecting (history 400) is ignored; a sent message is ignored
    fake["g_messages"] = {"old": (400, ["INBOX"], b"Subject: old\n\nold"),
                          "m1": (501, ["INBOX", "UNREAD"],
                                 PHISH.replace("you@example.com", "me@gmail.com").encode()),
                          "s1": (502, ["SENT", "INBOX"], b"Subject: mine\n\nhi")}
    fake["g_history"] = 502
    assert client.post(f"/api/v1/mailboxes/{mb['id']}/check", headers=A).status_code == 202
    items = wait_for(lambda: client.get("/api/v1/analyses?mine=true",
                                        headers=A).json()["items"])
    a = wait_done(client, items[0]["id"])
    items = client.get("/api/v1/analyses?mine=true", headers=A).json()["items"]
    assert len(items) == 1, "only mail after connecting is scanned"
    a = client.get(f"/api/v1/analyses/{a['id']}", headers=A).json()
    assert a["source"] == "mailbox" and a["visibility"] == "private" and a["label"] == "SCAM"
    assert a["mailbox_id"] == mb["id"]
    assert client.get(f"/api/v1/analyses/{a['id']}", headers=B).json()["mailbox_id"] is None
    assert "me@gmail.com" not in a["email"]["text"] + a["email"]["to"]
    wait_for(lambda: fake["g_modified"], 10)
    assert fake["g_modified"] == [("m1", ["Label_1", "STARRED"])]
    assert fake["g_labels"][0]["name"] == "AEGIS/Scam"
    listed = client.get("/api/v1/mailboxes", headers=A).json()[0]
    assert listed["scanned"] == 1 and listed["flagged"] == 1
    assert a["id"] not in {i["id"] for i in client.get("/api/v1/analyses").json()["items"]}

    # reconnecting the same account updates it instead of adding a second one
    state = start(client, A, fake)
    callback(client, A, code="good-code", state=state)
    assert len(client.get("/api/v1/mailboxes", headers=A).json()) == 1

    assert client.delete(f"/api/v1/mailboxes/{mb['id']}?purge=true", headers=A).status_code == 204
    assert fake["revoked"] == ["rt-secret-1"]
    assert client.get(f"/api/v1/analyses/{a['id']}").status_code == 404


# --------------------------------------------------------------------------- Outlook

def test_microsoft_connect_poll_label_rotate(oauth_env, client, fake):
    now = time.time()
    fake["ms_messages"] = [{"id": "AAold", "at": now - 3600, "draft": False,
                            "raw": b"Subject: old\n\nold"}]
    state = start(client, A, fake, "microsoft")
    assert callback(client, A, "microsoft", code="good-code",
                    state=state) == "/inbox?signin=connected"
    mb = client.get("/api/v1/mailboxes", headers=A).json()[0]
    assert mb["provider"] == "microsoft" and mb["email"] == "me@outlook.com"
    assert mb["label_mode"] == "outlook" and mb["manage_url"] == microsoft.MANAGE_URL

    fake["ms_messages"] += [
        {"id": "AAnew=", "at": now + 5, "draft": False,
         "raw": PHISH.replace("you@example.com", "me@outlook.com").encode()},
        {"id": "AAdraft", "at": now + 6, "draft": True, "raw": b"Subject: draft\n\nx"},
    ]
    assert client.post(f"/api/v1/mailboxes/{mb['id']}/check", headers=A).status_code == 202
    items = wait_for(lambda: client.get("/api/v1/analyses?mine=true",
                                        headers=A).json()["items"])
    a = wait_done(client, items[0]["id"])
    assert len(client.get("/api/v1/analyses?mine=true", headers=A).json()["items"]) == 1
    a = client.get(f"/api/v1/analyses/{a['id']}", headers=A).json()
    assert a["label"] == "SCAM" and "me@outlook.com" not in a["email"]["text"]
    wait_for(lambda: fake["ms_patched"], 10)
    assert fake["ms_patched"] == [("AAnew=", {"categories": ["Blue category", "AEGIS/Scam"],
                                              "flag": {"flagStatus": "flagged"}})]

    # the same-second message is not analyzed twice on the next poll
    before = client.get("/api/v1/mailboxes", headers=A).json()[0]["last_checked_at"]
    client.post(f"/api/v1/mailboxes/{mb['id']}/check", headers=A)
    after = wait_for(lambda: (m := client.get("/api/v1/mailboxes", headers=A).json()[0])
                     ["last_checked_at"] != before and m)
    assert after["status"] == "active" and after["last_error"] is None
    assert len(client.get("/api/v1/analyses?mine=true", headers=A).json()["items"]) == 1
    assert fake["ms_downloads"] == ["AAnew="]                        # downloaded once

    # Microsoft rotates refresh tokens: the new one is stored (encrypted) and used
    from aegis.core import crypto
    from aegis.db.models import Mailbox
    from aegis.db.session import session_scope

    async def stored():
        async with session_scope() as s:
            m = await s.get(Mailbox, mb["id"])
            return crypto.decrypt(m.secret, m.id), m.secret
    plain, cipher = client.portal.call(stored)
    assert plain == "rt-ms-2" and "rt-ms" not in cipher
    assert fake["ms_refresh_seen"][0] == "rt-ms-1"

    assert client.delete(f"/api/v1/mailboxes/{mb['id']}", headers=A).status_code == 204
    assert fake["revoked"] == []          # Graph has no per-app revoke; token deleted locally
