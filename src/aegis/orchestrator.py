"""Orchestrator: the AEGIS pipeline.

Triage → fan-out (forensic + vision + sandbox, in parallel) → threat graph
→ arbiter → verdict card. Individual stages fail closed: an exception in any
non-triage stage degrades the verdict toward SUSPICIOUS, never toward safe.
"""
from __future__ import annotations

import concurrent.futures
import sys
import time
from dataclasses import dataclass, field

from .agents import triage as triage_mod
from .agents.arbiter import Verdict, arbitrate
from .agents.forensic import ForensicReport, analyze as forensic_analyze
from .agents.sandbox import SandboxVerdict, inspect_urls
from .agents.signals import SignalReport, analyze_signals
from .agents.vision_inspector import VisionVerdict
from .graph.store import EmailEntities, ThreatGraph
from .verdict import DEFAULT_ACTION_PLANS, RedFlag, VerdictCard, render

MAX_SANDBOX_URLS = 5


@dataclass
class AnalysisResult:
    email_id: str
    triage: triage_mod.TriageResult | None = None
    signals: SignalReport | None = None
    forensic: ForensicReport | None = None
    vision: VisionVerdict | None = None
    sandbox: list[SandboxVerdict] = field(default_factory=list)
    verdict: Verdict | None = None
    card_markdown: str = ""
    campaign_note: str = ""
    # Per-stage latency + outcome, for the dashboard and eval. A failed
    # stage records {"ok": False} — the arbiter fails closed on the rest.
    stage_timings: dict = field(default_factory=dict)


def _timed(stage: str, fn, *args, **kwargs):
    """Run a stage, returning (result, timing_dict). Never raises."""
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        return result, {"seconds": round(time.time() - t0, 2), "ok": True}
    except Exception as e:  # noqa: BLE001 — the pipeline must never crash
        print(f"[aegis] stage '{stage}' failed, degrading: {e}",
              file=sys.stderr)
        return None, {"seconds": round(time.time() - t0, 2), "ok": False,
                      "error": str(e)[:200]}


def analyze_email(email_id: str, raw_body: str, headers: str = "",
                  html: str = "",
                  agentboxd_scores: dict | None = None) -> AnalysisResult:
    res = AnalysisResult(email_id=email_id)

    # Stage 1 — triage: always on. If the LLM is unreachable, this raises and
    # the caller (webhook) logs it; nothing is sent to the user.
    t0 = time.time()
    res.triage = triage_mod.triage(raw_body, headers)
    res.stage_timings["triage"] = {"seconds": round(time.time() - t0, 2),
                                   "ok": True}

    # Stage 1b — deterministic security signals: pure functions over the
    # artifact, no LLM. These are VERIFIED FACTS the forensic analyst
    # reasons over (instead of re-deriving them and possibly hallucinating).
    t0 = time.time()
    triage_dict = res.triage.__dict__
    res.signals = analyze_signals(raw_body, headers, html, triage_dict)
    res.stage_timings["signals"] = {"seconds": round(time.time() - t0, 2),
                                    "ok": True}
    signals_ctx = "\n".join(
        f"- [{s.severity}] {s.name}: {s.detail} (evidence: {s.evidence})"
        for s in res.signals.signals) or "(no deterministic signals fired)"

    # Stage 2 — parallel fan-out. Forensic, vision, and sandbox are
    # independent given triage, so they run concurrently. One stage failing
    # degrades that signal to None (arbiter fails closed) without touching
    # the others. Timings are recorded for the dashboard and eval.
    ab = agentboxd_scores or {}
    jobs: dict[str, tuple] = {
        "forensic": (forensic_analyze, (raw_body, headers),
                     {"triage": {**triage_dict,
                                 "deterministic_signals": signals_ctx},
                      "agentboxd_scores": {
                          "phishing": ab.get("phishing"),
                          "injection": ab.get("injection")}}),
    }
    if html:
        from .agents.vision_inspector import inspect as vision_inspect
        jobs["vision"] = (vision_inspect, (html,), {})
    if res.triage.urls:
        jobs["sandbox"] = (inspect_urls,
                           (res.triage.urls[:MAX_SANDBOX_URLS],), {})

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(jobs)) as pool:
        futures = {pool.submit(_timed, name, fn, *a, **k): name
                   for name, (fn, a, k) in jobs.items()}
        results = {}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            result, timing = fut.result()
            results[name] = result
            res.stage_timings[name] = timing

    res.forensic = results.get("forensic")
    res.vision = results.get("vision")
    res.sandbox = results.get("sandbox") or []

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
        explanation = graph.explain_campaign(email_id)
        res.campaign_note = (
            f"Linked to a known scam campaign — {others} related emails "
            f"share infrastructure with this one. {explanation}"
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
    # Deterministic signals are verified facts — high-severity ones join
    # the card directly, each citing the artifact it came from.
    if res.signals:
        flags += [RedFlag(s.detail, s.evidence)
                  for s in res.signals.signals if s.severity == "high"]
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
