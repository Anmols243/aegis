"""Orchestrator: the AEGIS pipeline.

Triage → fan-out (forensic + vision + sandbox) → threat graph → arbiter
→ verdict card. Individual stages fail closed: an exception in any
non-triage stage degrades the verdict toward SUSPICIOUS, never toward safe.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from .agents import triage as triage_mod
from .agents.arbiter import Verdict, arbitrate
from .agents.forensic import ForensicReport, analyze as forensic_analyze
from .agents.sandbox import SandboxVerdict, inspect_urls
from .agents.vision_inspector import VisionVerdict
from .graph.store import EmailEntities, ThreatGraph
from .verdict import DEFAULT_ACTION_PLANS, RedFlag, VerdictCard, render

MAX_SANDBOX_URLS = 5


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


def _try(stage: str, fn, *args, **kwargs):
    """Run a stage; on failure log and return None (arbiter fails closed)."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — the pipeline must never crash on a stage
        print(f"[aegis] stage '{stage}' failed, degrading: {e}", file=sys.stderr)
        return None


def analyze_email(email_id: str, raw_body: str, headers: str = "",
                  html: str = "",
                  agentboxd_scores: dict | None = None) -> AnalysisResult:
    res = AnalysisResult(email_id=email_id)

    # Stage 1 — triage: always on. If the LLM is unreachable, this raises and
    # the caller (webhook) logs it; nothing is sent to the user.
    res.triage = triage_mod.triage(raw_body, headers)

    # Stage 2 — fan-out.
    ab = agentboxd_scores or {}
    res.forensic = _try(
        "forensic", forensic_analyze,
        raw_body, headers,
        triage=res.triage.__dict__,
        agentboxd_scores={"phishing": ab.get("phishing"),
                         "injection": ab.get("injection")},
    )
    if html:
        from .agents.vision_inspector import inspect as vision_inspect
        res.vision = _try("vision", vision_inspect, html)
    if res.triage.urls:
        from .agents.sandbox import inspect_urls
        res.sandbox = _try("sandbox", inspect_urls,
                           res.triage.urls[:MAX_SANDBOX_URLS]) or []

    # Stage 3 — threat-intel graph.
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

    # Stage 4 — arbitrate.
    res.verdict = arbitrate({
        "agentboxd_phishing": ab.get("phishing"),
        "forensic": res.forensic.risk_score if res.forensic else None,
        "vision": res.vision.risk if res.vision else None,
        "sandbox": max((s.risk for s in res.sandbox), default=None),
    })

    # Stage 5 — verdict card.
    flags: list[RedFlag] = []
    if res.forensic:
        flags += [RedFlag(f.claim, f.evidence.excerpt)
                  for f in res.forensic.findings if f.severity == "high"]
    if res.vision and res.vision.impersonated_brand:
        flags.append(RedFlag(
            f"Visual impersonation of {res.vision.impersonated_brand}",
            res.vision.reason or "screenshot analysis"))
    for s in res.sandbox:
        if s.kind.value == "credential-harvest":
            flags.append(RedFlag("Link leads to a credential-harvesting page",
                                 s.final_url or s.url))
    card = VerdictCard(
        verdict=res.verdict,
        red_flags=flags[:6],
        action_plan=DEFAULT_ACTION_PLANS[res.verdict.label],
        campaign_note=res.campaign_note,
    )
    res.card_markdown = render(card)
    return res
