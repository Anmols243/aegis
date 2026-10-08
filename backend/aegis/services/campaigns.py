"""Threat-intel graph: link analyzed emails into scam campaigns.

Each analysis stores its infrastructure indicators as `entities`
(sender address, domain, URL, phone, body-template fingerprint). Two emails are
related when they share indicators; the relationship has a strength and a
human-readable reason. A campaign is a connected group of flagged emails
(SCAM / SUSPICIOUS) joined by at least medium-strength relationships.

Shared free-webmail domains (gmail.com, ...) are never treated as shared
infrastructure, so unrelated senders on the same provider do not merge.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from ..db.models import Analysis, Entity
from ..db.session import iso

WEBMAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
           "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com",
           "gmx.com", "mail.com", "zoho.com", "yandex.com"}
STRONG = {"sender", "domain", "phone"}
FLAGGED = {"SCAM", "SUSPICIOUS"}


def template_fingerprint(body: str) -> str:
    """Fingerprint of the message template: volatile tokens masked, then hashed."""
    norm = (body or "").lower()
    norm = re.sub(r"https?://\S+", " url ", norm)
    norm = re.sub(r"\b[\w.+-]+@[\w.-]+\b", " email ", norm)
    norm = re.sub(r"\d+", " n ", norm)
    norm = re.sub(r"[^a-z ]+", " ", norm)
    words = norm.split()
    if len(words) < 12:
        return ""   # too short to be a meaningful template
    return hashlib.sha256(" ".join(words).encode()).hexdigest()[:24]


def indicators(triage, body: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    m = re.search(r"[\w.+-]+@([\w-]+\.)+[\w-]+", triage.sender or "")
    if m:
        out.add(("sender", m.group(0).lower()))
    for d in triage.domains:
        d = d.lower().strip(".")
        if d and d not in WEBMAIL:
            out.add(("domain", d))
    for u in triage.urls:
        p = urlsplit(u)
        if p.hostname:
            out.add(("url", f"{p.hostname.lower()}{p.path}"))
    for ph in triage.phone_numbers:
        digits = re.sub(r"\D", "", ph)
        if len(digits) >= 7:
            out.add(("phone", digits))
    tpl = template_fingerprint(body)
    if tpl:
        out.add(("template", tpl))
    return out


@dataclass
class Relationship:
    analysis_id: str
    subject: str
    label: str | None
    strength: str
    why: str
    shared: list[str]

    def public(self) -> dict:
        return {"analysis_id": self.analysis_id, "subject": self.subject, "label": self.label,
                "strength": self.strength, "why": self.why, "shared": self.shared}


def strength_of(shared: list[tuple[str, str]]) -> tuple[str, str]:
    kinds = [k for k, _ in shared]
    strong = sum(1 for k in kinds if k in STRONG)
    pretty = " + ".join(sorted(set(kinds)))
    if strong >= 2 or len(shared) >= 4:
        return "high", f"shares {pretty}"
    if strong >= 1 or len(shared) >= 2:
        return "medium", f"shares {pretty}"
    return "weak", f"shares only {pretty}"


async def record(session, analysis_id: str, found: set[tuple[str, str]]) -> None:
    await session.execute(delete(Entity).where(Entity.analysis_id == analysis_id))
    session.add_all(Entity(analysis_id=analysis_id, kind=k, value=v[:500]) for k, v in found)
    await session.flush()


async def _load(session) -> tuple[dict[str, dict], dict[str, set[tuple[str, str]]]]:
    rows = (await session.execute(
        select(Analysis.id, Analysis.subject, Analysis.label, Analysis.created_at,
               Analysis.visibility, Analysis.owner_hash)
        .where(Analysis.source != "redteam", Analysis.status != "failed"))).all()
    meta = {r.id: {"subject": r.subject, "label": r.label, "created_at": r.created_at,
                   "visibility": r.visibility, "owner": r.owner_hash} for r in rows}
    ents: dict[str, set[tuple[str, str]]] = {}
    for e in (await session.execute(select(Entity))).scalars():
        if e.analysis_id in meta:
            ents.setdefault(e.analysis_id, set()).add((e.kind, e.value))
    return meta, ents


def _pairs(ents: dict[str, set[tuple[str, str]]]):
    by_value: dict[tuple[str, str], list[str]] = {}
    for aid, items in ents.items():
        for it in items:
            by_value.setdefault(it, []).append(aid)
    shared: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for it, aids in by_value.items():
        if len(aids) < 2 or len(aids) > 200:
            continue  # ubiquitous indicators carry no linking signal
        for i, a in enumerate(aids):
            for b in aids[i + 1:]:
                key = (a, b) if a < b else (b, a)
                shared.setdefault(key, []).append(it)
    return shared


async def relationships(session, analysis_id: str) -> list[Relationship]:
    meta, ents = await _load(session)
    rels = []
    for (a, b), items in _pairs(ents).items():
        if analysis_id not in (a, b):
            continue
        other = b if a == analysis_id else a
        strength, why = strength_of(items)
        rels.append(Relationship(other, meta[other]["subject"], meta[other]["label"],
                                 strength, why, sorted(f"{k}:{v}" for k, v in items)[:8]))
    order = {"high": 0, "medium": 1, "weak": 2}
    rels.sort(key=lambda r: (order[r.strength], r.analysis_id))
    return rels


async def campaigns(session, viewer: str | None = None) -> dict:
    """Campaigns as seen by one viewer. Grouping uses every flagged email (so
    private mail still strengthens threat intel), but only members the viewer
    may list are returned; the rest are counted in `hidden_count`."""
    meta, ents = await _load(session)

    def visible(aid: str) -> bool:
        m = meta[aid]
        return m["visibility"] == "public" or (viewer is not None and m["owner"] == viewer)

    pairs = {k: v for k, v in _pairs(ents).items()
             if strength_of(v)[0] in ("high", "medium")
             and meta[k[0]]["label"] in FLAGGED and meta[k[1]]["label"] in FLAGGED}
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        parent[find(a)] = find(b)
    groups: dict[str, set[str]] = {}
    for a, b in pairs:
        groups.setdefault(find(a), set()).update((a, b))

    out, nodes, links, seen_nodes = [], [], [], set()
    for members in sorted(groups.values(), key=lambda m: -len(m)):
        ordered_all = sorted(members, key=lambda m: meta[m]["created_at"])
        # hash the whole id: its leading hex is a timestamp, so a prefix collides
        # for analyses created within seconds of each other
        cid = "c_" + hashlib.sha256(ordered_all[0].encode()).hexdigest()[:10]
        ordered = [m for m in ordered_all if visible(m)]
        if not ordered:
            continue  # nothing this viewer may see
        # infrastructure is shown only as it appears in emails this viewer can see
        vis_items = set().union(*(ents.get(m, set()) for m in ordered))
        shared_items = sorted({it for (a, b), items in pairs.items()
                               if a in members for it in items} & vis_items)
        kinds = sorted({k for k, _ in shared_items}) or ["infrastructure"]
        out.append({
            "id": cid,
            "analyses": [{"id": m, "subject": meta[m]["subject"], "label": meta[m]["label"],
                          "created_at": iso(meta[m]["created_at"])}
                         for m in ordered],
            "hidden_count": len(ordered_all) - len(ordered),
            "infra": [{"kind": k, "value": v} for k, v in shared_items[:20]],
            "explanation": (f"{len(members)} flagged emails share {', '.join(kinds)}: "
                            f"the same operator infrastructure reused across messages."),
        })
        for m in ordered:
            nid = f"a:{m}"
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({"id": nid, "kind": "analysis", "label": meta[m]["subject"][:60],
                              "verdict": meta[m]["label"], "campaign": cid})
            for k, v in ents.get(m, ()):
                if (k, v) not in shared_items:
                    continue
                inid = f"{k}:{v}"
                if inid not in seen_nodes:
                    seen_nodes.add(inid)
                    nodes.append({"id": inid, "kind": k, "label": v[:60] if k != "template"
                                  else "same message template", "verdict": None, "campaign": cid})
                links.append({"source": nid, "target": inid})
    return {"campaigns": out, "graph": {"nodes": nodes, "links": links}}


async def campaign_id_for(session, analysis_id: str) -> str | None:
    meta, _ = await _load(session)
    owner = meta.get(analysis_id, {}).get("owner")
    for c in (await campaigns(session, viewer=owner))["campaigns"]:
        if any(a["id"] == analysis_id for a in c["analyses"]):
            return c["id"]
    return None
