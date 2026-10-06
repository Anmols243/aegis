"""Shared HTTP hardening for the AEGIS FastAPI apps.

- RateLimitMiddleware: in-memory token-bucket per client key. Rejects
  with 429 when the bucket is empty. Single-process safe; good enough
  for a webhook receiver and a demo dashboard.
- SecurityHeadersMiddleware: baseline headers so the dashboard page
  can't be clickjacked or MIME-sniffed.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket: `rate` tokens per `per_seconds`, burst up to `burst`."""

    def __init__(self, app, rate: float = 1.0, per_seconds: float = 60.0,
                 burst: int = 30, key_fn=None):
        super().__init__(app)
        self.rate = rate
        self.per_seconds = per_seconds
        self.burst = burst
        self.key_fn = key_fn or (lambda req: req.client.host
                                 if req.client else "unknown")
        self._buckets: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(burst), time.monotonic()))

    def _allowed(self, key: str) -> tuple[bool, float]:
        tokens, last = self._buckets[key]
        now = time.monotonic()
        tokens = min(self.burst, tokens + (now - last) * self.rate
                     / self.per_seconds)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True, 0.0
        retry = (1.0 - tokens) * self.per_seconds / self.rate
        self._buckets[key] = (tokens, now)
        return False, retry

    async def dispatch(self, request: Request, call_next):
        # Health checks and static assets never count against the budget.
        if request.url.path in ("/health", "/pixel-stars.js",
                                "/sonar-grid.js"):
            return await call_next(request)
        ok, retry_after = self._allowed(self.key_fn(request))
        if not ok:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        # The dashboard is token-authed; never allow framing it.
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "frame-ancestors 'none'"
        )
        return resp
