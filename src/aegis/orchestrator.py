"""Orchestrator: the AEGIS pipeline. Triage → fan-out → graph → arbiter → reply."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .agents import triage as triage_mod
from .agents.arbiter import Verdict, arbitrate
from .agents.forensic import ForensicReport
from .agents.sandbox import SandboxVerdict
from .agents.vision_inspector import VisionVerdict
from .graph.store import EmailEntities, ThreatGraph
from .verdict import DEFAULT_ACTION_PLANS, RedFlag, VerdictCard, render


@dataclass
class AnalysisResult:
    email_id: str
    triage: triage_mod.TriageResult | None = None
    forensic: ForensicReport | None = None
    vision: VisionVerdict | None = None
    sandbox: list[SandboxVerdict] = field(default_factory=list)
    verdict: Verdict | None = None
    card_markdown: str = ""
    campaign_note: str = ""


def _signals(res: AnalysisResult, agentboxd_phishing: float | None) -> dict:
    forensic_score = res.forensic.risk_score if res.forensic else None
    vision_score = res.vision.risk if res.vision else None
    sandbox_score = max((s.risk for s in res.sandbox), default=None)
    return {
        "agentboxd_phishing": agentboxd_phishing,
        "forensic": forensic_score,
        "vision": vision_score,
        "sandbox": sandbox_score,
    }


def analyze_email(email_id: str, raw_body: str, headers: str = "",
                  agentboxd_scores: dict | None = None) -> AnalysisResult:
    """Synchronous pipeline. Parallel stages move to asyncio in Phase 3+."""
    res = AnalysisResult(email_id=email_id)

    # Stage 1: triage (always on)
    res.triage = triage_mod.triage(raw_body, headers)

    # Stage 2: fan-out (Phase 2+ each; skipped until implemented)
    try:
        from .agents.forensic import analyze as forensic_analyze
        res.forensic = forensic_analyze(
            raw_body, headers,
            triage=res.triage.__dict__,
            agentboxd_scores=agentboxd_scores,
        )
    except NotImplementedError:
        pass

    # Stage 3: threat graph
    graph = ThreatGraph()
    graph.add_email(EmailEntities(
        email_id=email_id,
        senders=[res.triage.sender] if res.triage.sender else [],
        domains=res.triage.domains,
        urls=res.triage.urls,
        phones=res.triage.phone_numbers,
        body=raw_body,
    ))
    camp = graph.campaign_for(email_id)
    if camp:
        others = sum(1 for n in camp if n.startswith("email:"))
        res.campaign_note = (
            f"Linked to a known scam campaign — {others} related emails "
            f"share infrastructure with this one."
        )

    # Stage 4: arbitrate
    phishing = (agentboxd_scores or {}).get("phishing")
    res.verdict = arbitrate(_signals(res, phishing))

    # Stage 5: render verdict card
    flags = [
        RedFlag(f.claim, f.evidence.excerpt)
        for f in (res.forensic.findings if res.forensic else [])
        if f.severity == "high"
    ][:5]
    card = VerdictCard(
        verdict=res.verdict,
        red_flags=flags,
        action_plan=DEFAULT_ACTION_PLANS[res.verdict.label],
        campaign_note=res.campaign_note,
    )
    res.card_markdown = render(card)
    return res


# TODO (Phase 2): reply_to_email via AgentBoxD with res.card_markdown.
# High-risk outbound (warning third parties) → create_draft for human approval.
