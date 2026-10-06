"""Arbiter: weighted ensemble over normalized signals → verdict.

Fail-closed: missing or erroring signals are dropped and weights renormalized;
if the forensic signal is absent the label is capped at SUSPICIOUS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Label(str, Enum):
    SCAM = "SCAM"
    SUSPICIOUS = "SUSPICIOUS"
    LIKELY_SAFE = "LIKELY_SAFE"


WEIGHTS = {
    "agentboxd_phishing": 0.20,  # AgentBoxD per-message phishing score, 0..1
    "forensic": 0.35,            # forensic analyst risk_score, 0..1
    "vision": 0.20,              # 1.0 if brand impersonation found else 0.0 (scaled by confidence)
    "sandbox": 0.25,            # 1.0 credential-harvest, 0.6 malware-drop, 0.1 benign, 0.3 unreachable
}

THRESHOLD_SCAM = 0.70
THRESHOLD_SUSPICIOUS = 0.40


@dataclass
class Verdict:
    label: Label
    confidence: float  # 0..1, margin from the nearest decision boundary.
    # NOTE: this is a heuristic distance, NOT a statistically calibrated
    # probability. It is reported as "confidence" and never as P(malicious).
    score: float       # raw weighted score
    contributions: dict[str, float] = field(default_factory=dict)
    dissent: list[str] = field(default_factory=list)
    # --- explanation layer (added without touching score/threshold math) ---
    strongest: list[str] = field(default_factory=list)  # top contributors
    weakest: list[str] = field(default_factory=list)   # lowest contributors
    agreement: str = "unknown"  # unanimous | majority | split
    evidence_completeness: float = 0.0  # fraction of expected signals present


def arbitrate(signals: dict[str, float | None]) -> Verdict:
    """signals: name → 0..1 risk, or None if the stage errored/was skipped."""
    present = {k: v for k, v in signals.items() if v is not None and k in WEIGHTS}
    if not present:
        return Verdict(Label.SUSPICIOUS, 0.5, 0.5,
                       {}, ["no signals available — failing closed"])

    total_w = sum(WEIGHTS[k] for k in present)
    contributions = {k: (WEIGHTS[k] / total_w) * v for k, v in present.items()}
    score = sum(contributions.values())

    dissent: list[str] = []
    vals = list(present.values())
    if max(vals) - min(vals) > 0.5:
        hi = max(present, key=lambda k: present[k])  # type: ignore[arg-type]
        lo = min(present, key=lambda k: present[k])  # type: ignore[arg-type]
        dissent.append(
            f"agents disagree: {hi}={present[hi]:.2f} vs {lo}={present[lo]:.2f}"
        )

    if score >= THRESHOLD_SCAM:
        label = Label.SCAM
    elif score >= THRESHOLD_SUSPICIOUS:
        label = Label.SUSPICIOUS
    else:
        label = Label.LIKELY_SAFE

    # Fail closed: without the forensic analyst, never clear as safe.
    if "forensic" not in present and label == Label.LIKELY_SAFE:
        label = Label.SUSPICIOUS
        dissent.append("forensic analysis missing — capped at SUSPICIOUS")

    # Confidence = margin from the nearest decision boundary, scaled.
    # Heuristic only — see the Verdict docstring: never a calibrated P().
    if label == Label.SCAM:
        confidence = min(1.0, (score - THRESHOLD_SCAM) / (1.0 - THRESHOLD_SCAM) * 0.7 + 0.3)
    elif label == Label.SUSPICIOUS:
        mid = (THRESHOLD_SCAM + THRESHOLD_SUSPICIOUS) / 2
        confidence = 0.5 + 0.3 * (1 - abs(score - mid) / (mid - THRESHOLD_SUSPICIOUS))
    else:
        confidence = min(1.0, (THRESHOLD_SUSPICIOUS - score) / THRESHOLD_SUSPICIOUS * 0.7 + 0.3)

    # --- explanation layer: who drove the verdict, and did they agree? ---
    ranked = sorted(contributions.items(), key=lambda kv: kv[1],
                    reverse=True)
    strongest = [k for k, _ in ranked[:2] if ranked and ranked[0][1] > 0]
    weakest = [k for k, _ in ranked[-2:] if k not in strongest]
    spread = max(vals) - min(vals)
    agreement = ("unanimous" if spread <= 0.2
                 else "majority" if spread <= 0.5 else "split")
    evidence_completeness = round(len(present) / len(WEIGHTS), 2)

    return Verdict(label, round(confidence, 2), round(score, 3), contributions,
                   dissent, strongest, weakest, agreement,
                   evidence_completeness)
