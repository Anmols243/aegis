"""Render the user-facing verdict card (markdown, sent as the email reply)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .agents.arbiter import Label, Verdict

_EMOJI = {Label.SCAM: "🛑", Label.SUSPICIOUS: "⚠️", Label.LIKELY_SAFE: "✅"}


@dataclass
class RedFlag:
    title: str
    evidence: str  # quoted artifact excerpt


@dataclass
class VerdictCard:
    verdict: Verdict
    red_flags: list[RedFlag] = field(default_factory=list)
    action_plan: list[str] = field(default_factory=list)
    campaign_note: str = ""


def render(card: VerdictCard) -> str:
    v = card.verdict
    bar = "█" * int(v.confidence * 10) + "░" * (10 - int(v.confidence * 10))
    lines = [
        f"{_EMOJI[v.label]} **AEGIS verdict: {v.label.value}**",
        f"Confidence `{bar}` {v.confidence:.0%} · score {v.score:.2f}",
        "",
    ]
    if card.red_flags:
        lines.append("**Red flags**")
        for f in card.red_flags:
            lines.append(f"- **{f.title}** — _{f.evidence}_")
        lines.append("")
    if v.strongest:
        lines.append("**Strongest signals**")
        for s in v.strongest:
            lines.append(f"- {s} ({v.contributions.get(s, 0):.2f})")
        lines.append(f"_Signal agreement: {v.agreement} · "
                     f"evidence completeness {v.evidence_completeness:.0%}_")
        lines.append("")
    if v.dissent:
        lines.append("**Analyst notes**")
        for d in v.dissent:
            lines.append(f"- {d}")
        lines.append("")
    if card.campaign_note:
        lines.append(f"🕸️ {card.campaign_note}")
        lines.append("")
    if card.action_plan:
        lines.append("**What to do next**")
        for i, step in enumerate(card.action_plan, 1):
            lines.append(f"{i}. {step}")
        lines.append("")
    lines.append("— _Analyzed by AEGIS · every claim above cites the evidence it came from_")
    return "\n".join(lines)


DEFAULT_ACTION_PLANS = {
    Label.SCAM: [
        "Do not click any link, download anything, or reply.",
        "If you entered credentials anywhere, change that password now and enable 2FA.",
        "Report it: forward to your organization's security team or reportphishing@apwg.org.",
    ],
    Label.SUSPICIOUS: [
        "Do not click links yet — verify via a separate channel (official app or phone number from the company's real site).",
        "Check the sender address character-by-character for lookalikes.",
        "When in doubt, delete it. Legitimate senders will reach you again.",
    ],
    Label.LIKELY_SAFE: [
        "No action needed, but stay alert: this verdict covers this message only.",
        "If anything about it still feels off, forward it to us again with context.",
    ],
}
