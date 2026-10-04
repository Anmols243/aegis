"""Live dashboard API + page.

Run:  uvicorn aegis.dashboard.app:app --port 8001   (from the repo root)

The webhook receiver records every verdict into data/dashboard.db;
this app serves them as JSON plus the live frontend.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from . import store

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    p = HERE
    while not (p / "src" / "aegis").exists():
        p = p.parent
        if p == p.parent:
            return HERE.parents[2]
    return p


ROOT = _repo_root()
os.chdir(ROOT)

app = FastAPI(title="AEGIS live dashboard")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "live.html")


@app.get("/api/stats")
def api_stats() -> JSONResponse:
    return JSONResponse(store.stats())


@app.get("/api/verdicts")
def api_verdicts(limit: int = 50) -> JSONResponse:
    return JSONResponse(store.list_verdicts(min(limit, 200)))


@app.get("/api/verdicts/{email_id}")
def api_verdict(email_id: str) -> JSONResponse:
    v = store.get_verdict(email_id)
    if v is None:
        raise HTTPException(status_code=404, detail="unknown email_id")
    return JSONResponse(v)


@app.get("/api/campaigns")
def api_campaigns() -> JSONResponse:
    from ..graph.store import ThreatGraph
    out = []
    for camp in ThreatGraph().campaigns():
        emails = sorted(n.split("email:", 1)[1]
                        for n in camp if n.startswith("email:"))
        infra = sorted(n for n in camp if not n.startswith("email:"))
        out.append({"emails": emails, "n_emails": len(emails),
                    "infra": infra[:12], "n_infra": len(infra)})
    out.sort(key=lambda c: -c["n_emails"])
    return JSONResponse(out)


@app.get("/api/redteam")
def api_redteam() -> JSONResponse:
    cases = []
    for path in sorted(glob.glob("tests/regression/rt-*.json")):
        with open(path) as f:
            d = json.load(f)
        cases.append({
            "id": d.get("id"),
            "actual_label": d.get("actual_label"),
            "expected_label": d.get("expected_label"),
            "score": d.get("score"),
            "mutation_axes": d.get("mutation_axes", []),
            "caught_after_fix": d.get("caught_after_fix", False),
            "first_missed_at": d.get("first_missed_at"),
        })
    missed = sum(1 for c in cases
                 if c["actual_label"] != c["expected_label"]
                 and not c["caught_after_fix"])
    return JSONResponse({"total": len(cases), "open_misses": missed,
                         "cases": cases})
