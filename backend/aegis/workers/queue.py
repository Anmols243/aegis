"""DB-backed job queue. The `analyses` table is the queue.

- Jobs survive restarts: anything left `running` by a crash goes back to `queued`.
- A job is marked done only after the pipeline finished and the result was saved.
- Failures are retried with exponential backoff up to `max_attempts`.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from ..core.config import Settings
from ..core.events import bus
from ..core.logging import get_logger
from ..db.models import Analysis
from ..db.session import session_scope
from ..providers.agentboxd import AgentBoxD
from ..providers.llm import LLMClient
from ..services import analysis as svc

log = get_logger("queue")


class Worker:
    def __init__(self, settings: Settings, llm: LLMClient, agentboxd: AgentBoxD):
        self.s, self.llm, self.agentboxd = settings, llm, agentboxd
        self._wake = asyncio.Event()
        self._claim_lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []

    def notify(self) -> None:
        self._wake.set()

    async def start(self) -> None:
        async with session_scope() as s:
            await s.execute(update(Analysis).where(Analysis.status == "running")
                            .values(status="queued"))
        self._tasks = [asyncio.create_task(self._loop(i))
                       for i in range(max(1, self.s.worker_concurrency))]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def _claim(self) -> str | None:
        now = datetime.now(timezone.utc)
        async with self._claim_lock:
            async with session_scope() as s:
                a = (await s.execute(
                    select(Analysis).where(Analysis.status == "queued",
                                           or_(Analysis.next_attempt_at.is_(None),
                                               Analysis.next_attempt_at <= now))
                    .order_by(Analysis.created_at).limit(1))).scalar_one_or_none()
                if a is None:
                    return None
                a.status, a.attempts = "running", a.attempts + 1
                return a.id

    async def _loop(self, n: int) -> None:
        while True:
            try:
                job = await self._claim()
                if job is None:
                    self._wake.clear()
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                    continue
                await self._run(job)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - the loop itself must never die
                log.exception("worker loop error", extra={"worker": n})
                await asyncio.sleep(1.0)

    async def _run(self, analysis_id: str) -> None:
        try:
            await svc.process(analysis_id, self.s, self.llm, self.agentboxd)
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:300]}"
            async with session_scope() as s:
                a = await s.get(Analysis, analysis_id)
                if a is None:
                    return
                if a.attempts < self.s.max_attempts:
                    a.status = "queued"
                    a.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                        seconds=5 * 2 ** (a.attempts - 1))
                    a.error = f"attempt {a.attempts} failed: {err}"
                    final = False
                else:
                    a.status, a.error, final = "failed", err, True
            log.warning("analysis failed", extra={"analysis_id": analysis_id, "error": err,
                                                  "final": final})
            if final:
                bus.publish(analysis_id, "done", {"id": analysis_id, "status": "failed",
                                                  "error": err})
            else:
                bus.publish(analysis_id, "status", {"status": "queued", "retry": True})
            return
        await svc.maybe_reply(analysis_id, self.s, self.agentboxd)
        from ..services.mailboxes import label_verdict
        await label_verdict(analysis_id)
