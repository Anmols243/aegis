"""Viewer identity. The Next.js proxy gives each browser a random token in an
HttpOnly cookie and forwards it as X-Aegis-Viewer. Only its SHA-256 hash is
stored or compared; knowing the token is what proves ownership."""
from __future__ import annotations

import hashlib
import re

from fastapi import HTTPException, Request

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


def viewer_hash(request: Request) -> str | None:
    token = request.headers.get("x-aegis-viewer", "")
    if not _TOKEN.match(token):
        return None
    return hashlib.sha256(token.encode()).hexdigest()


def require_viewer(request: Request) -> str:
    v = viewer_hash(request)
    if v is None:
        raise HTTPException(403, "a browser session is required for this action")
    return v
