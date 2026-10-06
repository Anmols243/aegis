"""Stage 8: the human-facing report. Red flags with their evidence, plain-language
next steps tailored to what was found, and the verdict card sent by email."""
from __future__ import annotations

from .context import PipelineContext, StageResult

BASE_ACTIONS = {
    "SCAM": [
        "Do not click any link, open attachments, or reply.",
        "Report it: forward the email to reportphishing@apwg.org, and in the US to reportfraud.ftc.gov.",
        "Delete it once reported.",
    ],
    "SUSPICIOUS": [
        "Do not click links yet. Verify through a separate channel: the company's official app, "
        "or a phone number from its real website (not from this email).",
        "Check the sender address character by character for lookalikes.",
        "When in doubt, delete it. A legitimate sender will reach you again.",
    ],
    "LIKELY_SAFE": [
        "No action needed, but this verdict covers this message only.",
        "If something still feels off, verify with the sender through a channel you already trust.",
    ],
}


def tailored_actions(label: str, ctx: PipelineContext) -> list[str]:
    acts: list[str] = []
    r = ctx.results
    sandbox = r.get("sandbox") or []
    forensic = r.get("forensic")
    techniques = set(forensic.techniques) if forensic else set()
    if label != "LIKELY_SAFE":
        if any(v.kind == "credential-harvest" for v in sandbox) or "credential-harvest" in techniques:
            acts.append("If you already typed a password on a linked page, change it now "
                        "everywhere you reuse it and turn on two-factor authentication.")
        if "callback-scam" in techniques or (r.get("triage") and r["triage"].phone_numbers):
            acts.append("Do not call phone numbers from this email. Real companies never ask you "
                        "to call an unknown number to fix your account.")
        if {"gift-card-fraud", "invoice-fraud", "advance-fee"} & techniques:
            acts.append("Do not send money, gift cards or payment details. Confirm any payment "
                        "request in person or by a known phone number.")
        if "malware-attachment" in techniques or any(v.kind == "malware-drop" for v in sandbox):
            acts.append("Do not open the attachment or downloaded file. If you did, disconnect "
                        "from the network and run a malware scan.")
    return acts + BASE_ACTIONS[label]


def red_flags(ctx: PipelineContext) -> list[dict]:
    r = ctx.results
    flags: list[dict] = []
    forensic = r.get("forensic")
    if forensic:
        flags += [{"title": f.claim, "evidence": f.excerpt, "source": "forensic",
                   "severity": f.severity} for f in forensic.findings if f.severity == "high"]
    signals = r.get("signals")
    if signals:
        flags += [{"title": s.detail, "evidence": s.evidence, "source": "signal",
                   "severity": "high"} for s in signals.high]
    vision = r.get("vision")
    if vision and vision.impersonated_brand:
        flags.append({"title": f"Visually imitates {vision.impersonated_brand}",
                      "evidence": vision.reason or "rendered screenshot", "source": "vision",
                      "severity": "high" if vision.confidence >= 0.7 else "medium"})
    for v in r.get("sandbox") or []:
        if v.kind in ("credential-harvest", "malware-drop"):
            flags.append({"title": "Link opens a page that asks for a password"
                          if v.kind == "credential-harvest" else "Link delivers a downloadable file",
                          "evidence": v.final_url or v.url, "source": "sandbox",
                          "severity": "high"})
    return flags[:8]


_EMOJI = {"SCAM": "\U0001F6D1", "SUSPICIOUS": "⚠️", "LIKELY_SAFE": "✅"}


def card_markdown(verdict, flags: list[dict], actions: list[str], campaign_note: str,
                  summary: str, degraded: bool) -> str:
    bar = "█" * int(verdict.confidence * 10) + "░" * (10 - int(verdict.confidence * 10))
    lines = [f"{_EMOJI[verdict.label]} **AEGIS verdict: {verdict.label.replace('_', ' ')}**",
             f"Confidence `{bar}` {verdict.confidence:.0%} (score {verdict.score:.2f})", ""]
    if summary:
        lines += [summary, ""]
    if degraded:
        lines += ["_Note: part of the analysis ran in fallback mode, so this verdict is "
                  "deliberately cautious._", ""]
    if flags:
        lines.append("**Red flags**")
        lines += [f"- **{f['title']}** (evidence: _{f['evidence']}_)" for f in flags]
        lines.append("")
    if verdict.corroboration:
        lines.append("**Independent confirmations**")
        lines += [f"- {c}" for c in verdict.corroboration]
        lines.append("")
    if campaign_note:
        lines += [f"**Campaign:** {campaign_note}", ""]
    lines.append("**What to do next**")
    lines += [f"{i}. {a}" for i, a in enumerate(actions, 1)]
    lines += ["", "_Analyzed by AEGIS. Every red flag above quotes the evidence it came from._"]
    return "\n".join(lines)


async def run(ctx: PipelineContext) -> StageResult:
    verdict = ctx.results["arbiter"]
    flags = red_flags(ctx)
    actions = tailored_actions(verdict.label, ctx)
    graph = ctx.results.get("graph") or {}
    forensic = ctx.results.get("forensic")
    triage = ctx.results.get("triage")
    degraded = bool((triage and triage.degraded) or forensic is None)
    summary = forensic.summary if forensic else ""
    card = card_markdown(verdict, flags, actions, graph.get("note", ""), summary, degraded)
    return StageResult({"red_flags": flags, "actions": actions, "card_markdown": card,
                        "summary": summary}, f"{len(flags)} red flag(s), {len(actions)} next steps")
