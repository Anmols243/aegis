"""DAG runner. Each stage starts as soon as its dependencies have finished, so
forensic, vision, sandbox and graph run concurrently. Every state change is
reported through `on_stage` (persisted + streamed to the browser).

A failed or skipped stage never blocks the others: downstream stages and the
arbiter treat its output as missing (fail closed). Only parse, arbiter and
report are essential; if one of them fails the analysis fails.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

from . import arbiter, forensic, graph, parse, report, sandbox, signals, triage, vision
from .context import PipelineContext, Skip


@dataclass(frozen=True)
class StageDef:
    name: str
    deps: tuple[str, ...]
    fn: Callable[[PipelineContext], Awaitable]
    timeout_s: float


STAGES: tuple[StageDef, ...] = (
    StageDef("parse", (), parse.run, 15),
    StageDef("triage", ("parse",), triage.run, 150),
    StageDef("signals", ("triage",), signals.run, 15),
    StageDef("forensic", ("signals",), forensic.run, 240),
    StageDef("vision", ("parse",), vision.run, 150),
    StageDef("sandbox", ("triage",), sandbox.run, 75),
    StageDef("graph", ("triage",), graph.run, 30),
    StageDef("arbiter", ("signals", "forensic", "vision", "sandbox", "graph"), arbiter.run, 10),
    StageDef("report", ("arbiter",), report.run, 10),
)
STAGE_NAMES = [s.name for s in STAGES]
ESSENTIAL = {"parse", "arbiter", "report"}

OnStage = Callable[..., Awaitable[None]]


class PipelineFailed(RuntimeError):
    pass


async def _execute(stage: StageDef, ctx: PipelineContext) -> dict:
    t0 = time.monotonic()
    try:
        res = await asyncio.wait_for(stage.fn(ctx), stage.timeout_s)
        ctx.results[stage.name] = res.value
        out = {"status": "done", "summary": res.summary[:500], "error": None}
    except Skip as s:
        out = {"status": "skipped", "summary": str(s)[:500], "error": None}
    except asyncio.TimeoutError:
        out = {"status": "failed", "summary": "", "error": f"timed out after {stage.timeout_s:.0f}s"}
    except Exception as e:  # noqa: BLE001 - a broken stage degrades the verdict, not the run
        out = {"status": "failed", "summary": "", "error": f"{type(e).__name__}: {str(e)[:300]}"}
    out["duration_s"] = round(time.monotonic() - t0, 2)
    return out


async def run_pipeline(ctx: PipelineContext, on_stage: OnStage) -> dict[str, dict]:
    finished: dict[str, dict] = {}
    running: dict[asyncio.Task, StageDef] = {}
    started: set[str] = set()
    while len(finished) < len(STAGES):
        for st in STAGES:
            if st.name not in started and all(d in finished for d in st.deps):
                started.add(st.name)
                await on_stage(st.name, "running",
                               started_at=datetime.now(timezone.utc))
                running[asyncio.create_task(_execute(st, ctx))] = st
        if not running:
            raise PipelineFailed("pipeline stalled: unsatisfiable dependencies")
        done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            st = running.pop(task)
            out = task.result()
            finished[st.name] = out
            await on_stage(st.name, out["status"], duration_s=out["duration_s"],
                           summary=out["summary"], error=out["error"])
            if st.name in ESSENTIAL and out["status"] != "done":
                for t in running:
                    t.cancel()
                raise PipelineFailed(f"essential stage {st.name} failed: {out['error']}")
    return finished
