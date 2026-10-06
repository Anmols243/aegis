"""Background loops for connected mailboxes and data retention."""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from ..core.config import Settings
from ..core.logging import get_logger
from ..db.models import Mailbox
from ..db.session import session_scope
from ..services import analysis as svc
from ..services import mailboxes

log = get_logger("mailbox-worker")


class MailboxPoller:
    def __init__(self, settings: Settings, on_enqueue):
        self.s, self.on_enqueue = settings, on_enqueue
        self._tasks: list[asyncio.Task] = []
        self._kick = asyncio.Event()
        self._pending: set[str] = set()

    def trigger(self, mailbox_id: str) -> None:
        self._pending.add(mailbox_id)
        self._kick.set()

    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self._poll_loop()),
                       asyncio.create_task(self._retention_loop())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _poll_once(self, ids: list[str]) -> None:
        for mid in ids:
            try:
                n = await mailboxes.poll(mid)
            except Exception:  # noqa: BLE001
                log.exception("mailbox poll crashed", extra={"mailbox_id": mid})
                continue
            if n:
                log.info("mailbox mail queued", extra={"mailbox_id": mid, "count": n})
                self.on_enqueue()

    async def _poll_loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._kick.wait(), timeout=self.s.mailbox_poll_interval_s)
                self._kick.clear()
                ids, self._pending = list(self._pending), set()
            except asyncio.TimeoutError:
                async with session_scope() as s:
                    ids = list((await s.execute(select(Mailbox.id).where(
                        Mailbox.status != "paused"))).scalars())
            await self._poll_once(ids)

    async def _retention_loop(self) -> None:
        while True:
            try:
                n = await svc.purge_expired()
                if n:
                    log.info("retention purge", extra={"purged": n})
            except Exception:  # noqa: BLE001
                log.exception("retention purge failed")
            await asyncio.sleep(3600)
