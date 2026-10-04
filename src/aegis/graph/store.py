"""Threat-intel graph: link analyzed emails into scam campaigns.

Nodes: email, sender, domain, ip, url, phone, template_hash.
An email's infrastructure nodes are all linked to its email node; a campaign is
a connected component sharing >=2 infrastructure nodes (so one shared URL
shortener alone doesn't merge campaigns).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field

import networkx as nx

INFRA_TYPES = {"sender", "domain", "ip", "url", "phone", "template_hash"}


def template_hash(body: str) -> str:
    """Simhash-ish fingerprint: normalize, mask volatile tokens, hash shingles."""
    norm = body.lower()
    norm = re.sub(r"https?://\S+", " URL ", norm)
    norm = re.sub(r"\b\d[\d\s\-()]{5,}\b", " NUM ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    words = norm.split()
    shingles = {" ".join(words[i:i + 4]) for i in range(max(1, len(words) - 3))}
    digest = 0
    for s in shingles:
        h = int(hashlib.sha256(s.encode()).hexdigest(), 16)
        digest ^= h
    return f"tpl:{digest:064x}"


@dataclass
class EmailEntities:
    email_id: str
    senders: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    ips: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    body: str = ""


class ThreatGraph:
    def __init__(self, path: str = "data/threat_graph.json"):
        self.path = path
        self.g = nx.Graph()
        if os.path.exists(path):
            self.load()

    # -- mutation ------------------------------------------------------
    def add_email(self, e: EmailEntities) -> None:
        email_node = f"email:{e.email_id}"
        self.g.add_node(email_node, type="email")
        infra: list[str] = []
        for val, ntype in (
            *[(s, "sender") for s in e.senders],
            *[(d, "domain") for d in e.domains],
            *[(i, "ip") for i in e.ips],
            *[(u, "url") for u in e.urls],
            *[(p, "phone") for p in e.phones],
        ):
            node = f"{ntype}:{val.lower().strip()}"
            self.g.add_node(node, type=ntype)
            self.g.add_edge(email_node, node)
            infra.append(node)
        if e.body:
            tnode = template_hash(e.body)
            self.g.add_node(tnode, type="template_hash")
            self.g.add_edge(email_node, tnode)
            infra.append(tnode)
        # link infra nodes to each other so campaigns cluster without the email node
        for a in infra:
            for b in infra:
                if a < b:
                    self.g.add_edge(a, b)
        self.save()

    # -- queries -------------------------------------------------------
    def campaigns(self, min_shared_infra: int = 2) -> list[set[str]]:
        """Connected components over infra nodes with >= min_shared_infra nodes
        and at least 2 emails behind them."""
        infra_only = self.g.subgraph(
            [n for n, d in self.g.nodes(data=True) if d.get("type") in INFRA_TYPES]
        )
        out = []
        for comp in nx.connected_components(infra_only):
            emails = {
                m for n in comp for m in self.g.neighbors(n)
                if self.g.nodes[m].get("type") == "email"
            }
            if len(comp) >= min_shared_infra and len(emails) >= 2:
                out.append(set(comp) | emails)
        return out

    def campaign_for(self, email_id: str) -> set[str] | None:
        node = f"email:{email_id}"
        for camp in self.campaigns():
            if node in camp:
                return camp
        return None

    # -- persistence ---------------------------------------------------
    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {
            "nodes": [[n, dict(d)] for n, d in self.g.nodes(data=True)],
            "edges": list(self.g.edges()),
        }
        with open(self.path, "w") as f:
            json.dump(data, f)

    def load(self) -> None:
        with open(self.path) as f:
            data = json.load(f)
        self.g = nx.Graph()
        self.g.add_nodes_from([(n, d) for n, d in data["nodes"]])
        self.g.add_edges_from([tuple(e) for e in data["edges"]])
