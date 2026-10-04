"""Link sandbox: isolated URL inspection.

CONTRACT (Phase 4):
  inspect_url(url: str) -> SandboxVerdict
  inspect_urls(urls: list[str]) -> list[SandboxVerdict]  (concurrent, bounded)

SECURITY CONTRACT (non-negotiable):
- No JavaScript execution. Static fetch + screenshot of the static render only.
- SSRF deny-list: 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1,
  link-local, and any DNS that resolves into those ranges. Resolve-then-check.
- 10s timeout, max 5 redirects, 5MB response cap.
- NEVER submit forms, NEVER send credentials, NEVER follow `javascript:` URLs.
- A dumb fetch is a feature: a smart fetch is an attack surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ipaddress


class PageKind(str, Enum):
    CREDENTIAL_HARVEST = "credential-harvest"
    MALWARE_DROP = "malware-drop"
    BENIGN = "benign"
    UNREACHABLE = "unreachable"


_SSRF_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def is_blocked_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(addr in net for net in _SSRF_NETWORKS)


@dataclass
class SandboxVerdict:
    url: str
    final_url: str = ""
    kind: PageKind = PageKind.UNREACHABLE
    status_code: int | None = None
    screenshot_path: str = ""
    note: str = ""

    @property
    def risk(self) -> float:
        return {
            PageKind.CREDENTIAL_HARVEST: 1.0,
            PageKind.MALWARE_DROP: 0.6,
            PageKind.UNREACHABLE: 0.3,
            PageKind.BENIGN: 0.1,
        }[self.kind]


def inspect_url(url: str) -> SandboxVerdict:
    """Phase 4: guarded fetch → screenshot → MODEL_VISION or heuristic classify."""
    raise NotImplementedError("Phase 4 — see BUILD_PLAN.md")
