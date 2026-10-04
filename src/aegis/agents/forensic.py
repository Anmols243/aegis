"""Forensic analyst: long-context, evidence-cited scam analysis.

Every finding MUST quote the artifact it came from. A finding without a
quotation is dropped — the citation requirement is what keeps this from
being a generic LLM summary.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_settings
from ..llm import chat_json

FORENSIC_SYSTEM = """You are AEGIS-Forensic, an email forensics analyst.
Analyze the email for scam / impersonation / fraud indicators.

Return ONLY valid JSON:
{
  "findings": [
    {"claim": "one sentence", "severity": "high|medium|low",
     "evidence": {"artifact": "header|body|url|attachment", "excerpt": "exact quote"}}
  ],
  "deception_techniques": ["spoofed-sender", "lookalike-domain", "urgency-pressure",
     "authority-impersonation", "credential-harvest", "invoice-fraud", "callback-scam"],
  "risk_score": 0.0-1.0,
  "summary": "two sentences, plain language"
}

Rules:
- EVERY finding needs an exact excerpt quote from the email. No quote → drop the finding.
- risk_score is your calibrated estimate that this email is malicious.
- Consider: authentication results, reply-to vs from mismatch, lookalike
  domains (homoglyphs, added words), urgency/threat language, mismatched
  branding, URL vs display-text mismatch, unusual attachment types."""

TECHNIQUE_TAXONOMY = [
    "spoofed-sender", "lookalike-domain", "urgency-pressure",
    "authority-impersonation", "credential-harvest", "invoice-fraud",
    "callback-scam", "qr-code-lure",
]


@dataclass
class Evidence:
    artifact: str
    excerpt: str


@dataclass
class Finding:
    claim: str
    severity: str
    evidence: Evidence


@dataclass
class ForensicReport:
    findings: list[Finding] = field(default_factory=list)
    deception_techniques: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    summary: str = ""


def analyze(raw_email: str, headers: str = "",
            triage: dict | None = None,
            agentboxd_scores: dict | None = None) -> ForensicReport:
    """Run the forensic analyst. Returns an evidence-cited report."""
    model = get_settings().model_forensic
    context = [f"HEADERS:\n{headers}", f"BODY:\n{raw_email}"]
    if triage:
        context.append("TRIAGE ENTITIES:\n" + str(triage))
    if agentboxd_scores:
        context.append("AGENTBOXD SCORES:\n" + str(agentboxd_scores))
    data = chat_json(
        model,
        [
            {"role": "system", "content": FORENSIC_SYSTEM},
            {"role": "user", "content": "\n\n".join(context)},
        ],
    )
    findings = []
    for f in data.get("findings", []):
        ev = f.get("evidence", {})
        # Enforce the citation rule: no excerpt, no finding.
        if not ev.get("excerpt"):
            continue
        findings.append(Finding(
            claim=f.get("claim", ""),
            severity=f.get("severity", "low"),
            evidence=Evidence(ev.get("artifact", "body"), ev["excerpt"]),
        ))
    techniques = [t for t in data.get("deception_techniques", [])
                  if t in TECHNIQUE_TAXONOMY]
    return ForensicReport(
        findings=findings,
        deception_techniques=techniques,
        risk_score=float(data.get("risk_score", 0.0)),
        summary=data.get("summary", ""),
    )
