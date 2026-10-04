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

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import store

HERE = Path(__file__).resolve().parent

# Dashboard security: local/demo use needs nothing. If you expose this
# beyond localhost, set AEGIS_DASHBOARD_TOKEN — every route then requires
# ?token=<value> or an Authorization: Bearer header.
DASHBOARD_TOKEN = os.environ.get("AEGIS_DASHBOARD_TOKEN")


def _require_token(request: Request) -> None:
    if not DASHBOARD_TOKEN:
        return
    if request.query_params.get("token") == DASHBOARD_TOKEN:
        return
    auth = request.headers.get("authorization", "")
    if auth == f"Bearer {DASHBOARD_TOKEN}":
        return
    raise HTTPException(status_code=401, detail="dashboard token required")


if not DASHBOARD_TOKEN:
    print("[aegis] dashboard auth disabled — bind to 127.0.0.1 only "
          "unless you set AEGIS_DASHBOARD_TOKEN", flush=True)


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
def index(request: Request, _auth: None = Depends(_require_token)
          ) -> FileResponse:
    return FileResponse(HERE / "live.html")


@app.get("/api/stats")
def api_stats(request: Request, _auth: None = Depends(_require_token)
              ) -> JSONResponse:
    return JSONResponse(store.stats())


@app.get("/api/verdicts")
def api_verdicts(request: Request, limit: int = 50,
                 _auth: None = Depends(_require_token)) -> JSONResponse:
    return JSONResponse(store.list_verdicts(min(limit, 200)))


@app.get("/api/verdicts/{email_id}")
def api_verdict(request: Request, email_id: str,
                _auth: None = Depends(_require_token)) -> JSONResponse:
    v = store.get_verdict(email_id)
    if v is None:
        raise HTTPException(status_code=404, detail="unknown email_id")
    return JSONResponse(v)


@app.get("/api/action-plans")
def api_action_plans(request: Request,
                     _auth: None = Depends(_require_token)) -> JSONResponse:
    from ..verdict import DEFAULT_ACTION_PLANS
    return JSONResponse({label.value: plan
                         for label, plan in DEFAULT_ACTION_PLANS.items()})


@app.get("/api/campaigns")
def api_campaigns(request: Request,
                  _auth: None = Depends(_require_token)) -> JSONResponse:
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
def api_redteam(request: Request,
                _auth: None = Depends(_require_token)) -> JSONResponse:
    from ..agents.redteam import regression_summary
    summary = regression_summary()
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
    summary["cases"] = cases
    return JSONResponse(summary)
