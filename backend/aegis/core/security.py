"""HTTP hardening: API-key auth, per-client rate limits, streaming body limits,
security headers. Middlewares are pure ASGI so SSE streams are never buffered."""
from __future__ import annotations

import hmac
import json
import time

from fastapi import HTTPException, Request

from .config import get_settings


# --------------------------------------------------------------------------- auth

def bearer_ok(request: Request) -> bool:
    key = get_settings().aegis_api_key
    if not key:
        return True
    auth = request.headers.get("authorization", "")
    supplied = auth[7:] if auth.lower().startswith("bearer ") else ""
    return bool(supplied) and hmac.compare_digest(supplied.encode(), key.encode())


async def require_api_key(request: Request) -> None:
    if not bearer_ok(request):
        raise HTTPException(status_code=401, detail="valid API key required",
                            headers={"WWW-Authenticate": "Bearer"})


def client_ip(request: Request) -> str:
    """X-Forwarded-For is trusted only from an authenticated proxy (the Next.js app)."""
    s = get_settings()
    if s.trust_proxy_headers and s.aegis_api_key and bearer_ok(request):
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- rate limit

class TokenBucket:
    def __init__(self, per_min: float, burst: int):
        self.rate, self.burst = per_min / 60.0, burst
        self._b: dict[str, tuple[float, float]] = {}

    def take(self, key: str) -> float:
        """0 if allowed, else seconds until a token is available."""
        now = time.monotonic()
        tokens, last = self._b.get(key, (float(self.burst), now))
        tokens = min(self.burst, tokens + (now - last) * self.rate)
        if tokens >= 1.0:
            self._b[key] = (tokens - 1.0, now)
            if len(self._b) > 50_000:  # bound memory under a flood of unique keys
                self._b.clear()
            return 0.0
        self._b[key] = (tokens, now)
        return (1.0 - tokens) / self.rate


_submit: TokenBucket | None = None
_general: TokenBucket | None = None


def reset_limits() -> None:
    global _submit, _general
    s = get_settings()
    _submit = TokenBucket(s.submit_rate_per_min, s.submit_burst)
    _general = TokenBucket(s.general_rate_per_min, s.general_burst)


def _limit(bucket_name: str):
    async def dep(request: Request) -> None:
        if _submit is None:
            reset_limits()
        bucket = _submit if bucket_name == "submit" else _general
        wait = bucket.take(client_ip(request))
        if wait:
            raise HTTPException(status_code=429, detail="rate limit exceeded",
                                headers={"Retry-After": str(int(wait) + 1)})
    return dep


limit_submit = _limit("submit")
limit_general = _limit("general")


# --------------------------------------------------------------------------- middlewares

class BodyLimitMiddleware:
    """Reject oversized request bodies while they stream in, before any parsing
    or signature work (Content-Length is checked up front too)."""

    def __init__(self, app, default_limit: int, limits: dict[str, int]):
        self.app, self.default, self.limits = app, default_limit, limits

    def _limit_for(self, path: str) -> int:
        for prefix, n in self.limits.items():
            if path.startswith(prefix):
                return n
        return self.default

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        limit = self._limit_for(scope["path"])
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > limit:
                        return await self._reject(send)
                except ValueError:
                    return await self._reject(send, 400, "bad content-length")
        seen = 0

        async def limited_receive():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return msg

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send, status: int = 413, detail: str = "request body too large"):
        body = json.dumps({"detail": detail}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class _TooLarge(Exception):
    pass


class SecurityHeadersMiddleware:
    HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"no-referrer"),
        (b"x-frame-options", b"DENY"),
        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
        (b"cross-origin-resource-policy", b"same-origin"),
    ]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # The interactive API docs page loads Swagger UI from a CDN; it gets
        # every header except the strict CSP. All data routes keep the CSP.
        extra = (self.HEADERS[:3] if scope["path"] == "/api/docs" else self.HEADERS)

        async def send_with_headers(msg):
            if msg["type"] == "http.response.start":
                msg = dict(msg)
                msg["headers"] = list(msg.get("headers", [])) + extra
            await send(msg)

        await self.app(scope, receive, send_with_headers)
