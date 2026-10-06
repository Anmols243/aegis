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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import store
from ..middleware import RateLimitMiddleware, SecurityHeadersMiddleware

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

# The standalone Momen-copy frontend (tools/momen/copy) is hosted separately
# from this API, so it needs cross-origin GET access. The dashboard token
# stays in the query string; CORS does not weaken that check.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
# ~2 req/s sustained, burst 60: polling (10s) + human browsing stays well
# under; scrapers get 429s.
app.add_middleware(RateLimitMiddleware, rate=120.0, per_seconds=60.0,
                   burst=60)


@app.get("/")
def index(request: Request, _auth: None = Depends(_require_token)
          ) -> FileResponse:
    # no-store: the page is a single HTML file whose theme changes with deploys;
    # heuristic browser caching would otherwise show a stale theme.
    return FileResponse(HERE / "live.html",
                        headers={"Cache-Control": "no-store"})


@app.get("/pixel-stars.js")
def pixel_stars() -> FileResponse:
    # 16-bit starfield background, served as a separate file (no-store so
    # theme iterations reach visitors immediately).
    return FileResponse(HERE / "pixel-stars.js",
                        media_type="application/javascript",
                        headers={"Cache-Control": "no-store"})


@app.get("/sonar-grid.js")
def sonar_grid() -> FileResponse:
    # Sonar dot-grid background (default; ?bg=stars switches back).
    return FileResponse(HERE / "sonar-grid.js",
                        media_type="application/javascript",
                        headers={"Cache-Control": "no-store"})


@app.get("/api/stats")
def api_stats(request: Request, _auth: None = Depends(_require_token)
              ) -> JSONResponse:
    data = store.stats()
    data["blast"] = store.blast_status()
    return JSONResponse(data)


@app.get("/api/verdicts")
def api_verdicts(request: Request, limit: int = 50,
                 _auth: None = Depends(_require_token)) -> JSONResponse:
    return JSONResponse(store.list_verdicts(max(1, min(limit, 200))))


@app.get("/api/verdicts/{email_id}")
def api_verdict(request: Request, email_id: str,
                _auth: None = Depends(_require_token)) -> JSONResponse:
    if not email_id or len(email_id) > 128 or any(
            ord(c) < 32 for c in email_id):
        raise HTTPException(status_code=400, detail="invalid email_id")
    v = store.get_verdict(email_id)
    if v is None:
        raise HTTPException(status_code=404, detail="unknown email_id")
    return JSONResponse(v)


@app.get("/api/verdicts/{email_id}/abuse-report")
def api_abuse_report(request: Request, email_id: str,
                     _auth: None = Depends(_require_token)
                     ) -> JSONResponse:
    """Ready-to-send takedown report for one verdict.

    Uses the RAW (unredacted) record — a masked sender is useless in an
    abuse report. Same token auth as every other route.
    """
    if not email_id or len(email_id) > 128 or any(
            ord(c) < 32 for c in email_id):
        raise HTTPException(status_code=400, detail="invalid email_id")
    v = store.get_verdict(email_id, raw=True)
    if v is None:
        raise HTTPException(status_code=404, detail="unknown email_id")
    from ..abuse import build_abuse_report
    from ..graph.store import ThreatGraph
    infra = ThreatGraph().infra_for(email_id)
    return JSONResponse({"email_id": email_id,
                         "markdown": build_abuse_report(email_id, v, infra)})


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
