"""Optional AgentBoxD inbox poller (AGENTBOXD_POLL=true): an alternative to
webhooks that needs no public URL. Only mail arriving after startup is taken,
so old messages are never re-analyzed or auto-replied to."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from ..core.logging import get_logger
from ..db.models import Analysis
from ..db.session import session_scope
from ..providers.agentboxd import AgentBoxD, message_scores, message_to_raw
from ..services import analysis as svc

log = get_logger("poller")


async def poll_forever(agentboxd: AgentBoxD, on_enqueue) -> None:
    since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
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
            async with session_scope() as s:
                exists = (await s.execute(select(Analysis.id).where(
                    Analysis.external_id == mid))).scalar_one_or_none()
            if exists:
                continue
            msg = await agentboxd.get_message(mid)
            raw, html = message_to_raw(msg)
            async with session_scope() as s:
                await svc.create(s, source="poller", raw=raw, raw_html=html,
                                 provider_scores=message_scores(msg), external_id=mid,
                                 inbox_id=agentboxd.s.agentboxd_inbox_id)
            on_enqueue()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - survive network blips
            log.warning("poll error", extra={"error": str(e)[:200]})
            await asyncio.sleep(5)
