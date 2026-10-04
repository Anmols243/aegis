"""Forensic analyst: long-context, evidence-cited scam analysis.

CONTRACT (Phase 2):
  analyze(raw_email, headers, triage, agentboxd_scores) -> ForensicReport

Every finding MUST quote the artifact it came from. A finding without a
quotation is a failed output — the citation requirement is what keeps this
from being a generic LLM summary.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
- EVERY finding needs an exact excerpt quote. No quote → drop the finding.
- risk_score is your calibrated estimate that this email is malicious.
- Consider: authentication results, reply-to vs from mismatch, lookalike
  domains (homoglyphs, added words), urgency/threat language, mismatched
  branding, URL vs display-text mismatch, unusual attachment types.
"""

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
    """Phase 2: implement with MODEL_FORENSIC via llm.chat_json."""
    raise NotImplementedError("Phase 2 — see BUILD_PLAN.md")
