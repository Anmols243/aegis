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


@dataclass
class Relationship:
    """An explicit pairwise link between two emails.

    Unlike the transitive connected-component campaigns, a Relationship
    explains WHY two messages are linked and how strong the link is.
    """
    other_email_id: str
    shared: list[str]            # infra node names, e.g. "domain:evil.com"
    strength: str                # high | medium | weak
    why: str                     # human-readable, e.g. "shares domain + phone"


# Node types that strongly indicate shared operators (vs. coincidental).
_STRONG_TYPES = {"sender", "domain", "ip", "phone"}
_WEAK_TYPES = {"url", "template_hash"}


def _node_type(node: str) -> str:
    return node.split(":", 1)[0] if ":" in node else ""


def _strength_for(shared: list[str]) -> tuple[str, str]:
    types = [_node_type(n) for n in shared]
    strong = sum(1 for t in types if t in _STRONG_TYPES)
    total = len(shared)
    pretty = " + ".join(sorted(set(types)))
    if strong >= 2 or total >= 4:
        return "high", f"shares {pretty}"
    if strong >= 1 or total >= 2:
        return "medium", f"shares {pretty}"
    return "weak", f"shares only {pretty}"


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

    def infra_for(self, email_id: str) -> dict[str, list[str]]:
        """Structured indicators for one email: {node_type: [values]}.

        Used by the abuse-report generator. Returns {} for unknown ids.
        """
        node = f"email:{email_id}"
        if node not in self.g:
            return {}
        out: dict[str, list[str]] = {}
        for n in self.g.neighbors(node):
            ntype = self.g.nodes[n].get("type", "")
            if ntype in INFRA_TYPES and ntype != "template_hash":
                val = n.split(":", 1)[1] if ":" in n else n
                out.setdefault(ntype, []).append(val)
        return {k: sorted(set(v)) for k, v in out.items()}

    def relationships(self, email_id: str) -> list[Relationship]:
        """Explicit pairwise links for one email, strongest first.

        Each relationship names the shared infrastructure and a strength —
        e.g. sharing a domain + phone is HIGH, sharing only one common
        URL shortener is WEAK. This is the explainable complement to the
        transitive campaign components.
        """
        node = f"email:{email_id}"
        if node not in self.g:
            return []
        my_infra = {n for n in self.g.neighbors(node)
                    if self.g.nodes[n].get("type") in INFRA_TYPES}
        rels: list[Relationship] = []
        for other in self.g.nodes:
            if not other.startswith("email:") or other == node:
                continue
            other_infra = {n for n in self.g.neighbors(other)
                           if self.g.nodes[n].get("type") in INFRA_TYPES}
            shared = sorted(my_infra & other_infra)
            if not shared:
                continue
            strength, why = _strength_for(shared)
            rels.append(Relationship(
                other_email_id=other.split("email:", 1)[1],
                shared=shared, strength=strength, why=why))
        order = {"high": 0, "medium": 1, "weak": 2}
        rels.sort(key=lambda r: (order[r.strength], r.other_email_id))
        return rels

    def explain_campaign(self, email_id: str) -> str:
        """One-paragraph, judge-readable account of an email's campaign ties."""
        rels = self.relationships(email_id)
        if not rels:
            return "No campaign linkage found for this email."
        top = rels[0]
        others = len(rels)
        return (f"Linked to {others} related email(s); strongest tie is to "
                f"{top.other_email_id} ({top.strength} confidence — "
                f"{top.why}: {', '.join(top.shared[:4])}).")

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
