"""Phase 1 smoke test: triage a sample phishing email via Featherless.

Usage:  FEATHERLESS_API_KEY=... MODEL_TRIAGE=... python scripts/smoke_llm.py
Exits non-zero if the model doesn't return valid entity JSON.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegis.agents.triage import triage

SAMPLE_PHISH_HEADERS = """From: "PayPaI Security" <security@paypa1-secure.com>
Reply-To: support@paypa1-secure.com
Authentication-Results: spf=fail; dkim=fail; dmarc=fail"""

SAMPLE_PHISH_BODY = """Dear Customer,

We detected unusual activity on your PayPal account. Your account will be
limited within 24 hours unless you verify your identity immediately.

Verify now: http://paypa1-secure.com/verify?session=8f3k2

Failure to act will result in permanent suspension.

PayPal Security Team"""


def main() -> int:
    result = triage(SAMPLE_PHISH_BODY, SAMPLE_PHISH_HEADERS)
    print("sender:          ", result.sender)
    print("reply_to:        ", result.reply_to)
    print("urls:            ", result.urls)
    print("domains:         ", result.domains)
    print("urgency_signals: ", result.urgency_signals)
    print("requested_action:", result.requested_action)
    print("brand_mentions:  ", result.brand_mentions)
    assert "paypa1-secure.com" in result.domains, "triage missed the lookalike domain"
    assert result.urls, "triage missed the URL"
    print("\nSMOKE OK — triage returned valid entity JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
