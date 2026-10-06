"""Privacy model (unlisted analyses, redacted relations), credential encryption,
and retention. Mailbox sign-in is covered in test_oauth.py."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aegis.core import crypto
from aegis.services.samples import BY_ID

from .conftest import wait_done

A = {"X-Aegis-Viewer": "viewer-a-" + "a" * 40}
B = {"X-Aegis-Viewer": "viewer-b-" + "b" * 40}
PHISH = BY_ID["paypal-phish"]["raw"]


def submit(client, raw, headers):
    r = client.post("/api/v1/analyses", json={"raw": raw}, headers=headers)
    assert r.status_code == 202, r.text
    return r.json()["id"]


# --------------------------------------------------------------------------- crypto

def test_credentials_encrypted_and_bound(settings_env):
    crypto.reset_key_cache()
    token = crypto.encrypt("abcd efgh ijkl mnop", "mb_1")
    assert "abcd" not in token and token.startswith("v1:")
    assert crypto.decrypt(token, "mb_1") == "abcd efgh ijkl mnop"
    with pytest.raises(Exception):
        crypto.decrypt(token, "mb_2")            # bound to its mailbox id
    with pytest.raises(Exception):
        crypto.decrypt(token[:-2] + "AA", "mb_1")  # tampering is detected
    crypto.reset_key_cache()


# --------------------------------------------------------------------------- visibility

def test_pasted_mail_is_unlisted(client):
    aid = submit(client, "hi, the spare key is under the mat. see you friday", A)
    wait_done(client, aid)
    ids = lambda h: {i["id"] for i in client.get("/api/v1/analyses", headers=h).json()["items"]}  # noqa: E731
    assert aid in ids(A)
    assert aid not in ids(B) and aid not in ids({})
    mine = client.get("/api/v1/analyses?mine=true", headers=A).json()["items"]
    assert [i["id"] for i in mine] == [aid] and mine[0]["mine"] is True
    # capability link: the id itself still opens it, but it is not "mine" for others
    d = client.get(f"/api/v1/analyses/{aid}", headers=B).json()
    assert d["visibility"] == "private" and d["mine"] is False


def test_samples_are_public(client):
    r = client.post("/api/v1/analyses", json={"sample_id": "legit-receipt"}, headers=A)
    aid = r.json()["id"]
    wait_done(client, aid)
    assert aid in {i["id"] for i in client.get("/api/v1/analyses").json()["items"]}


def test_other_users_related_mail_is_anonymised(client):
    a_id = submit(client, PHISH, A)
    wait_done(client, a_id)
    b_id = submit(client, PHISH, B)
    b = wait_done(client, b_id)
    rel = b["campaign"]["related"]
    assert rel and all(r.get("private") for r in rel)
    assert all("analysis_id" not in r and "subject" not in r and "shared" not in r for r in rel)
    camps = client.get("/api/v1/campaigns", headers=B).json()["campaigns"]
    members = {x["id"] for c in camps for x in c["analyses"]}
    assert a_id not in members and b_id in members
    assert any(c["hidden_count"] >= 1 for c in camps)


def test_retention_purges_private_content(client):
    aid = submit(client, PHISH, A)
    wait_done(client, aid)
    from aegis.services import analysis as svc
    later = datetime.now(timezone.utc) + timedelta(days=8)
    assert client.portal.call(svc.purge_expired, later) >= 1
    d = client.get(f"/api/v1/analyses/{aid}", headers=A).json()
    assert d["purged"] is True
    assert d["email"]["text"] == "" and d["card_markdown"] == "" and d["triage"] is None
    assert all(f["excerpt"] == "" for f in d["findings"])
    assert d["label"] == "SCAM"                       # the verdict is kept
