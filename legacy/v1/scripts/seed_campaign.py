"""Seed a demo scam campaign into the threat-intel graph.

Adds three parcel-redelivery phishes sharing infrastructure (sender domain,
URL host, callback phone). A fourth email sharing >=2 of those infra nodes
will then cluster into the campaign, and the verdict card will cite it.

Deterministic — no LLM calls. Safe to re-run (ids are stable).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aegis.graph.store import EmailEntities, ThreatGraph

SEED = [
    EmailEntities(
        email_id="seed-parcel-001",
        senders=["ParcelTrack <notify@parcel-track-notify.com>"],
        domains=["parcel-track-notify.com"],
        urls=["http://parcel-track-notify.com/redelivery?pkg=88412"],
        phones=["+1-800-555-0142"],
        body=("Your parcel could not be delivered. Pay the $2.95 redelivery fee "
              "within 48 hours or it will be returned to sender. "
              "http://parcel-track-notify.com/redelivery?pkg=88412"),
    ),
    EmailEntities(
        email_id="seed-parcel-002",
        senders=["ParcelTrack <notify@parcel-track-notify.com>"],
        domains=["parcel-track-notify.com"],
        urls=["http://parcel-track-notify.com/redelivery?pkg=90177"],
        phones=["+1-800-555-0142"],
        body=("Delivery attempt failed for package 90177. A redelivery fee of $2.95 "
              "is due within 48 hours: http://parcel-track-notify.com/redelivery?pkg=90177 "
              "Questions? Call +1-800-555-0142."),
    ),
    EmailEntities(
        email_id="seed-parcel-003",
        senders=["ParcelTrack Support <support@parcel-track-notify.com>"],
        domains=["parcel-track-notify.com"],
        urls=["http://parcel-track-notify.com/pay?pkg=91523"],
        phones=["+1-800-555-0142"],
        body=("Final notice: package 91523 will be returned unless the $2.95 fee "
              "is paid today. http://parcel-track-notify.com/pay?pkg=91523"),
    ),
]


def main() -> None:
    g = ThreatGraph()
    for e in SEED:
        g.add_email(e)
    camp = g.campaign_for("seed-parcel-001")
    n_emails = sum(1 for n in (camp or set()) if n.startswith("email:"))
    print(f"seeded {len(SEED)} emails -> campaign with {n_emails} emails")
    if camp:
        infra = sorted(n for n in camp if not n.startswith("email:"))
        print("shared infra:", ", ".join(infra[:6]))
    assert camp and n_emails >= 3, "seeding failed to form a campaign"
    print("OK: campaign clusters")


if __name__ == "__main__":
    main()
