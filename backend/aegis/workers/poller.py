"""AgentBoxD inbox poller (on unless a webhook secret is set; AGENTBOXD_POLL forces it): the
webhooks that needs no public URL. Only mail arriving after startup is taken,
so old messages are never re-analyzed or auto-replied to."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from ..core.logging import get_logger
from ..db.models import Analysis
from ..db.session import session_scope
from ..providers.agentboxd import AgentBoxD, message_scores, message_to_raw
from ..services import analysis as svc

log = get_logger("poller")


def _after(ts: str) -> str:
    """ISO timestamp 1 ms later (same format AgentBoxD returns)."""
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00")) + timedelta(milliseconds=1)
    except ValueError:
        return ts
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def _retry_after(response: httpx.Response) -> float:
    """Seconds to back off after a 429: the API's hint, else the header, else 15."""
    try:
        hint = response.json()["error"]["details"]["retry_after_seconds"]
        return min(max(float(hint), 1.0), 120.0)
    except Exception:  # noqa: BLE001 - fall through to the header
        pass
    try:
        return min(max(float(response.headers.get("retry-after", "")), 1.0), 120.0)
    except ValueError:
        return 15.0


async def poll_forever(agentboxd: AgentBoxD, on_enqueue) -> None:
    since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    last_id = None
    log.info("poller started", extra={"inbox": agentboxd.s.agentboxd_inbox_id})
    while True:
        try:
            stub = await agentboxd.wait_inbound(since, timeout_s=55)
            if not stub:
                continue
            mid = stub.get("id")
            since = stub.get("received_at") or stub.get("created_at") or since
            if not mid:
                continue
            if mid == last_id:
                # the API returned the same message again (inclusive `since`):
                # step past it instead of spinning on it
                since = _after(since)
                continue
            last_id = mid
            async with session_scope() as s:
                exists = (await s.execute(select(Analysis.id).where(
                    Analysis.external_id == mid))).scalar_one_or_none()
            if exists:
                continue
            msg = await agentboxd.get_message(mid)
            if msg.get("withheld"):
                # held by AgentBoxD screening: only metadata comes back, nothing to analyze
                log.warning("message withheld by AgentBoxD screening",
                            extra={"message_id": mid,
                                   "reason": (msg.get("screening") or {}).get("reason")})
                continue
            raw, html = message_to_raw(msg)
            async with session_scope() as s:
                await svc.create(s, source="poller", raw=raw, raw_html=html,
                                 provider_scores=message_scores(msg), external_id=mid,
                                 inbox_id=agentboxd.s.agentboxd_inbox_id)
            on_enqueue()
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as e:
            wait = _retry_after(e.response) if e.response.status_code == 429 else 5
            log.warning("poll error", extra={"error": str(e)[:200], "retry_in_s": wait})
            await asyncio.sleep(wait)
        except Exception as e:  # noqa: BLE001 - survive network blips
            log.warning("poll error", extra={"error": str(e)[:200]})
            await asyncio.sleep(5)
