"""Sign in with a mail provider: OAuth 2.0 authorization code flow with PKCE.

Shared by providers/google.py (Gmail API) and providers/microsoft.py (Microsoft
Graph). Each provider module supplies its endpoints, scope check and mail
operations; this module holds the sign-in state and token handling.

Privacy and safety:
- AEGIS never sees the user's password; it gets a token limited to reading
  mail and tagging it.
- Only the refresh token is stored, encrypted (core/crypto.py). Access tokens
  live in memory for their lifetime (about an hour).
- Only fixed provider endpoints are called; no user-supplied URL is fetched.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx

TIMEOUT_S = 20.0
STATE_TTL_S = 600
MAX_MESSAGE_BYTES = 2 * 1024 * 1024


class OAuthError(Exception):
    """A failure with a message that is safe and useful to show the user."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_S)


def client() -> httpx.AsyncClient:
    """Provider modules call this (tests replace `_client` with a fake)."""
    return _client()


# --------------------------------------------------------------------------- sign-in state

# state -> pending sign-in. In memory: a sign-in takes a minute and the app is
# single-process (see ARCHITECTURE.md, known limits). A restart only means
# "try again".
#
# Status: pending (sent to the provider) -> exchanging -> connected, or
# -> confirm (the provider returned to a different browser than the one that
# started, e.g. AEGIS runs in an app's built-in browser that Google blocks)
# -> connected or cancelled; any step can end in error.
_pending: dict[str, dict] = {}


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def begin(prov, client_id: str, redirect_uri: str, owner_hash: str,
          retention_days: int) -> tuple[str, str, str]:
    """Remember a pending sign-in for this browser. Returns (consent URL, state,
    pairing code). The pairing code is shown in the starting window and again
    if the sign-in comes back in another browser, so the user can check both
    belong to the same sign-in."""
    now = time.time()
    for k in [k for k, v in _pending.items() if v["expires"] < now]:
        _pending.pop(k, None)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    pair = f"{secrets.randbelow(10_000):04d}"
    _pending[state] = {"provider": prov.ID, "owner": owner_hash, "verifier": verifier,
                       "pair": pair, "retention": retention_days,
                       "expires": now + STATE_TTL_S, "status": "pending"}
    url = prov.AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": prov.SCOPE, "state": state, "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256", **prov.AUTH_EXTRA,
    })
    return url, state, pair


def get_pending(state: str) -> dict:
    p = _pending.get(state or "")
    if p is None or p["expires"] < time.time():
        raise OAuthError("The sign-in expired. Please start again from AEGIS.")
    return p


# --------------------------------------------------------------------------- tokens

async def exchange(prov, client_id: str, secret: str, redirect_uri: str, code: str,
                   verifier: str) -> dict:
    async with client() as c:
        r = await c.post(prov.TOKEN_URL, data={
            "code": code, "client_id": client_id, "client_secret": secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
            "code_verifier": verifier})
    if r.status_code != 200:
        raise OAuthError(f"{prov.NAME} did not accept the sign-in. Please try again.")
    tok = r.json()
    if not prov.has_scope(str(tok.get("scope", ""))):
        raise OAuthError(f"AEGIS needs permission to read and tag your mail. Please sign in "
                         f"to {prov.NAME} again and allow it.")
    if not tok.get("refresh_token") or not tok.get("access_token"):
        raise OAuthError(f"{prov.NAME} did not return a long-lived token. Please try again.")
    return tok


# access tokens per mailbox: id -> (token, expires_at)
_access: dict[str, tuple[str, float]] = {}


async def access_token(prov, mailbox_id: str, client_id: str, secret: str,
                       refresh: str) -> tuple[str, str | None]:
    """(access token, rotated refresh token or None). Microsoft rotates refresh
    tokens; the caller stores the new one."""
    hit = _access.get(mailbox_id)
    if hit and hit[1] > time.time() + 60:
        return hit[0], None
    data = {"client_id": client_id, "client_secret": secret, "refresh_token": refresh,
            "grant_type": "refresh_token"}
    if prov.REFRESH_SCOPE:
        data["scope"] = prov.REFRESH_SCOPE
    async with client() as c:
        r = await c.post(prov.TOKEN_URL, data=data)
    if r.status_code in (400, 401):
        raise OAuthError(f"{prov.NAME} access was revoked or expired. Disconnect and sign "
                         f"in again.")
    if r.status_code != 200:
        raise OAuthError(f"{prov.NAME} sign-in service error ({r.status_code}).")
    tok = r.json()
    _access[mailbox_id] = (tok["access_token"], time.time() + int(tok.get("expires_in", 3600)))
    rotated = tok.get("refresh_token")
    return tok["access_token"], (rotated if rotated and rotated != refresh else None)


def forget(mailbox_id: str) -> None:
    _access.pop(mailbox_id, None)
