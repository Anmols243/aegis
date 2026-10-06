"""Outlook.com, Hotmail, Live and Microsoft 365 via Sign in with Microsoft
(OAuth flow in providers/oauth.py) and Microsoft Graph.

- Scopes: Mail.ReadWrite (read mail, set categories and flags; Graph has no
  narrower scope that allows tagging), User.Read (the address), offline_access.
  AEGIS never sends, moves or deletes mail.
- Cursor: the received time (epoch seconds) of the newest message seen; at
  sign-in it is "now", so only new mail is read. Messages at the same second
  are de-duplicated by id in services/mailboxes.py.
- Graph has no call to revoke one app's token, so disconnect deletes the token
  and the user is pointed at MANAGE_URL to remove AEGIS's permission.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from . import oauth
from .oauth import MAX_MESSAGE_BYTES, OAuthError

ID = "microsoft"
NAME = "Microsoft"
AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH = "https://graph.microsoft.com/v1.0/me"
SCOPE = ("offline_access https://graph.microsoft.com/Mail.ReadWrite "
         "https://graph.microsoft.com/User.Read")
AUTH_EXTRA = {"prompt": "select_account", "response_mode": "query"}
REFRESH_SCOPE = SCOPE
HOST = "graph.microsoft.com"
LABEL_MODE = "outlook"
MANAGE_URL = "https://account.live.com/consent/Manage"
CATEGORIES = {"SCAM": "AEGIS/Scam", "SUSPICIOUS": "AEGIS/Suspicious"}


def has_scope(granted: str) -> bool:
    return any(s.lower().endswith("mail.readwrite") for s in granted.split())


async def revoke(token: str) -> None:  # noqa: ARG001 - no per-app revocation in Graph
    return None


async def _call(token: str, method: str, path: str, raw: bool = False, **kw):
    async with oauth.client() as c:
        r = await c.request(method, GRAPH + path,
                            headers={"Authorization": f"Bearer {token}"}, **kw)
    if r.status_code in (401, 403):
        raise OAuthError("Outlook refused access. Disconnect and sign in with Microsoft again.")
    if r.status_code >= 400:
        raise OAuthError(f"Outlook error ({r.status_code}).")
    if raw:
        return r.content
    return r.json() if r.content else {}


def _epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


async def profile(token: str) -> tuple[str, int]:
    """(email address, cursor = now)."""
    me = await _call(token, "GET", "", params={"$select": "mail,userPrincipalName"})
    email = me.get("mail") or me.get("userPrincipalName") or ""
    if "@" not in email:
        raise OAuthError("This Microsoft account has no mailbox.")
    return email, int(time.time())


async def new_message_ids(token: str, cursor: int, limit: int) -> tuple[list[str], int]:
    """Ids of inbox messages received at or after the cursor, oldest first, and
    the cursor to continue from."""
    since = datetime.fromtimestamp(cursor, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    page = await _call(token, "GET", "/mailFolders/inbox/messages", params={
        "$filter": f"receivedDateTime ge {since}", "$orderby": "receivedDateTime asc",
        "$select": "id,receivedDateTime,isDraft", "$top": str(limit)})
    ids, latest = [], cursor
    for m in page.get("value", []):
        if m.get("isDraft") or not m.get("id"):
            continue
        ids.append(m["id"])
        latest = max(latest, _epoch(m["receivedDateTime"]))
    return ids, latest


async def raw_message(token: str, message_id: str) -> bytes:
    """The full MIME message. Reading it does not mark it read."""
    data = await _call(token, "GET", f"/messages/{message_id}/$value", raw=True)
    return b"" if len(data) > MAX_MESSAGE_BYTES else data


async def apply_label(token: str, message_id: str, verdict: str) -> None:
    """SCAM: AEGIS/Scam category + flag. SUSPICIOUS: AEGIS/Suspicious category.
    Never moves or deletes; keeps the message's existing categories."""
    m = await _call(token, "GET", f"/messages/{message_id}", params={"$select": "categories"})
    cats = list(dict.fromkeys([*m.get("categories", []), CATEGORIES[verdict]]))
    body: dict = {"categories": cats}
    if verdict == "SCAM":
        body["flag"] = {"flagStatus": "flagged"}
    await _call(token, "PATCH", f"/messages/{message_id}", json=body)
