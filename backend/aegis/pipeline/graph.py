"""Stage 6: record this email's infrastructure and link it to earlier emails."""
from __future__ import annotations

from ..db.session import session_scope
from ..services import campaigns
from .context import PipelineContext, Skip, StageResult


async def run(ctx: PipelineContext) -> StageResult:
    if ctx.source == "redteam":
        raise Skip("red-team variants stay out of the campaign graph")
    triage = ctx.results.get("triage")
    if triage is None:
        raise Skip("no entities extracted")
    found = campaigns.indicators(triage, ctx.email.text)
    async with session_scope() as s:
        await campaigns.record(s, ctx.analysis_id, found)
        rels = await campaigns.relationships(s, ctx.analysis_id)
    strong = [r for r in rels if r.strength != "weak"]
    if strong:
        top = strong[0]
        # No subject here: the related email may belong to someone else.
        note = (f"Linked to {len(strong)} earlier email(s) that share infrastructure. "
                f"Strongest tie: {top.strength} ({top.why}).")
        summary = f"linked to {len(strong)} email(s), strongest {top.strength}"
    else:
        note, summary = "", f"{len(found)} indicator(s) recorded, no campaign link yet"
    return StageResult({"related": [r.public() for r in rels[:10]], "note": note}, summary)
