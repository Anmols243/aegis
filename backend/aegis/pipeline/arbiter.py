"""Stage 7: the arbiter. Weighted ensemble plus a corroboration rule.

1. Weighted mean over the signals that are present (missing ones are dropped
   and the weights renormalised).
2. Corroboration: when two or more INDEPENDENT sources each report strong
   evidence (forensic risk >= 0.85, a high-severity deterministic signal, a
   credential-harvest or malware page, visual brand impersonation, the inbox
   provider's phishing score), the verdict is SCAM even if a weak source drags
   the mean down. A dead phishing domain (sandbox "unreachable") should not
   rescue an email two other agents independently convicted.
3. Fail closed: without the forensic analyst an email is never cleared as safe.

"Confidence" is distance from the nearest decision boundary: a heuristic,
never presented as a calibrated probability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .context import PipelineContext, StageResult

WEIGHTS = {"forensic": 0.35, "signals": 0.20, "sandbox": 0.15, "vision": 0.15,
           "agentboxd": 0.15}
THRESHOLD_SCAM = 0.70
THRESHOLD_SUSPICIOUS = 0.40


@dataclass
class Verdict:
    label: str
    score: float
    confidence: float
    contributions: dict[str, float] = field(default_factory=dict)
    dissent: list[str] = field(default_factory=list)
    strongest: list[str] = field(default_factory=list)
    weakest: list[str] = field(default_factory=list)
    agreement: str = "unknown"
    evidence_completeness: float = 0.0
    corroboration: list[str] = field(default_factory=list)

    def public(self) -> dict:
        return asdict(self)


def _confidence(label: str, score: float) -> float:
    if label == "SCAM":
        c = (score - THRESHOLD_SCAM) / (1 - THRESHOLD_SCAM) * 0.7 + 0.3
    elif label == "SUSPICIOUS":
        mid = (THRESHOLD_SCAM + THRESHOLD_SUSPICIOUS) / 2
        c = 0.5 + 0.3 * (1 - abs(score - mid) / (mid - THRESHOLD_SUSPICIOUS))
    else:
        c = (THRESHOLD_SUSPICIOUS - score) / THRESHOLD_SUSPICIOUS * 0.7 + 0.3
    return round(max(0.0, min(1.0, c)), 2)


def arbitrate(risks: dict[str, float | None], strong: list[str],
              applicable: set[str] | None = None) -> Verdict:
    """risks: source -> 0..1 or None. strong: independent strong-evidence notes."""
    present = {k: max(0.0, min(1.0, v)) for k, v in risks.items()
               if v is not None and k in WEIGHTS}
    applicable = applicable or set(WEIGHTS)
    if not present:
        return Verdict("SUSPICIOUS", 0.5, 0.5, dissent=["no signals available: failing closed"])

    total_w = sum(WEIGHTS[k] for k in present)
    contributions = {k: round(WEIGHTS[k] / total_w * v, 3) for k, v in present.items()}
    score = round(sum(contributions.values()), 3)
    dissent: list[str] = []

    label = ("SCAM" if score >= THRESHOLD_SCAM else
             "SUSPICIOUS" if score >= THRESHOLD_SUSPICIOUS else "LIKELY_SAFE")
    if len(strong) >= 2 and label != "SCAM":
        dissent.append(f"weighted score {score:.2f} overridden: {len(strong)} independent "
                       f"sources found strong evidence")
        label = "SCAM"
    if "forensic" not in present and label == "LIKELY_SAFE":
        label = "SUSPICIOUS"
        dissent.append("forensic analysis missing: capped at SUSPICIOUS")

    vals = list(present.values())
    spread = max(vals) - min(vals)
    if spread > 0.5:
        hi = max(present, key=present.get)
        lo = min(present, key=present.get)
        dissent.append(f"agents disagree: {hi}={present[hi]:.2f} vs {lo}={present[lo]:.2f}")
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    strongest = [k for k, v in ranked[:2] if v > 0]
    weakest = [k for k, _ in ranked[-2:] if k not in strongest]
    effective = max(score, THRESHOLD_SCAM) if label == "SCAM" else score
    return Verdict(
        label=label, score=score, confidence=_confidence(label, effective),
        contributions=contributions, dissent=dissent, strongest=strongest, weakest=weakest,
        agreement="unanimous" if spread <= 0.2 else "majority" if spread <= 0.5 else "split",
        evidence_completeness=round(len(present) / max(1, len(applicable & set(WEIGHTS))), 2),
        corroboration=strong)


def gather(ctx: PipelineContext) -> tuple[dict[str, float | None], list[str], set[str]]:
    r = ctx.results
    forensic, signals = r.get("forensic"), r.get("signals")
    vision, sandbox = r.get("vision"), r.get("sandbox")
    phishing = ctx.provider_scores.get("phishing")
    risks = {
        "forensic": forensic.risk_score if forensic else None,
        "signals": signals.risk if signals else None,
        "vision": vision.risk if vision else None,
        "sandbox": max((v.risk for v in sandbox), default=None) if sandbox else None,
        "agentboxd": phishing,
    }
    strong: list[str] = []
    if forensic and forensic.risk_score >= 0.85:
        strong.append(f"forensic analyst: risk {forensic.risk_score:.2f}")
    if signals and signals.high:
        strong.append(f"deterministic signal: {signals.high[0].name}")
    if vision and vision.impersonated_brand and vision.confidence >= 0.7:
        strong.append(f"vision: impersonates {vision.impersonated_brand}")
    if sandbox and any(v.kind in ("credential-harvest", "malware-drop") for v in sandbox):
        kind = next(v.kind for v in sandbox if v.kind in ("credential-harvest", "malware-drop"))
        strong.append(f"link sandbox: {kind} page")
    if phishing is not None and phishing >= 0.85:
        strong.append(f"AgentBoxD phishing score {phishing:.2f}")
    applicable = {"forensic", "signals"}
    if ctx.email and ctx.email.html:
        applicable.add("vision")
    if r.get("triage") and r["triage"].urls:
        applicable.add("sandbox")
    if phishing is not None:
        applicable.add("agentboxd")
    return risks, strong, applicable


async def run(ctx: PipelineContext) -> StageResult:
    risks, strong, applicable = gather(ctx)
    v = arbitrate(risks, strong, applicable)
    return StageResult(v, f"{v.label} at {v.score:.2f}"
                          + (f", {len(strong)} corroborating source(s)" if strong else ""))
