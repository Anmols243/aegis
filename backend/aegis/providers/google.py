"""Gmail via Sign in with Google (OAuth flow in providers/oauth.py).

- One scope, gmail.modify: read mail and add labels. AEGIS never sends,
  deletes or moves mail.
- Cursor: the Gmail history id at sign-in, so only new mail is read.
- Disconnecting revokes the token at Google, so access ends everywhere.
"""
from __future__ import annotations

import base64

import httpx

from . import oauth
from .oauth import MAX_MESSAGE_BYTES, OAuthError

ID = "google"
NAME = "Google"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPE = "https://www.googleapis.com/auth/gmail.modify"
AUTH_EXTRA = {"access_type": "offline", "prompt": "consent"}
REFRESH_SCOPE = None
HOST = "gmail.googleapis.com"
LABEL_MODE = "gmail-api"
MANAGE_URL = "https://myaccount.google.com/connections"
LABELS = {"SCAM": "AEGIS/Scam", "SUSPICIOUS": "AEGIS/Suspicious"}


def has_scope(granted: str) -> bool:
    return SCOPE in granted.split()


async def revoke(token: str) -> None:
    """Best effort: end AEGIS's access at Google."""
    try:
        async with oauth.client() as c:
            await c.post(REVOKE_URL, data={"token": token})
    except httpx.HTTPError:
        pass


class _HistoryExpired(Exception):
    pass


async def _call(token: str, method: str, path: str, **kw) -> dict:
    async with oauth.client() as c:
        r = await c.request(method, GMAIL + path,
                            headers={"Authorization": f"Bearer {token}"}, **kw)
    if r.status_code == 404 and path.startswith("/history"):
        raise _HistoryExpired()
    if r.status_code in (401, 403):
        raise OAuthError("Gmail refused access. Disconnect and sign in with Google again.")
    if r.status_code >= 400:
        raise OAuthError(f"Gmail error ({r.status_code}).")
    return r.json() if r.content else {}


async def profile(token: str) -> tuple[str, int]:
    """(email address, cursor = current history id)."""
    p = await _call(token, "GET", "/profile")
    return str(p["emailAddress"]), int(p["historyId"])


async def new_message_ids(token: str, start_history: int, limit: int) -> tuple[list[str], int]:
    """Ids of messages added to INBOX after the cursor, oldest first, and the
    cursor to continue from. A history id too old to list restarts at "now"."""
    ids: list[str] = []
    latest, page = start_history, None
    while True:
        params = {"startHistoryId": str(start_history), "historyTypes": "messageAdded",
                  "labelId": "INBOX", "maxResults": "100"}
        if page:
            params["pageToken"] = page
        try:
            h = await _call(token, "GET", "/history", params=params)
        except _HistoryExpired:
            return [], (await profile(token))[1]
        latest = max(latest, int(h.get("historyId", latest)))
        for rec in h.get("history", []):
            for added in rec.get("messagesAdded", []):
                m = added.get("message", {})
                labels = set(m.get("labelIds", []))
                if m.get("id") and "INBOX" in labels and not labels & {"SENT", "DRAFT"} \
                        and m["id"] not in ids:
                    ids.append(m["id"])
        page = h.get("nextPageToken")
        if not page or len(ids) >= limit:
            break
    return ids[:limit], latest


async def raw_message(token: str, message_id: str) -> bytes:
    """The full RFC 822 message. Reading it does not mark it read."""
    meta = await _call(token, "GET", f"/messages/{message_id}",
                       params={"format": "minimal"})
    if int(meta.get("sizeEstimate", 0)) > MAX_MESSAGE_BYTES:
        return b""
    m = await _call(token, "GET", f"/messages/{message_id}", params={"format": "raw"})
    raw = m.get("raw", "")
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)) if raw else b""


async def apply_label(token: str, message_id: str, verdict: str) -> None:
    """SCAM: AEGIS/Scam label + star. SUSPICIOUS: AEGIS/Suspicious label. Never
    moves, archives or deletes."""
    name = LABELS[verdict]
    existing = await _call(token, "GET", "/labels")
    label_id = next((lb["id"] for lb in existing.get("labels", []) if lb.get("name") == name),
                    None)
    if label_id is None:
        made = await _call(token, "POST", "/labels", json={
            "name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})
        label_id = made["id"]
    add = [label_id] + (["STARRED"] if verdict == "SCAM" else [])
    await _call(token, "POST", f"/messages/{message_id}/modify", json={"addLabelIds": add})
