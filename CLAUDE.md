# AEGIS: working notes for coding agents

Multi-agent, evidence-cited scam analysis. ForgeHacks 2026, AI + Cybersecurity track.
Deadline: Devpost locks Oct 10, 2026, 12:00 PM ET.

## Docs (read before changing behaviour)

- `README.md`: what it is, how to run it, what works and what does not.
- `ARCHITECTURE.md`: layout, pipeline, arbiter, security model.
- `docs/API.md`: the API contract. Frontend types in `frontend/lib/api.ts` mirror it; change both.
- `DECISIONS.md`: append-only decision log. `LOG.md`: session log, newest first.

## Commands

```bash
# backend (from backend/)
.venv/Scripts/python -m pytest -q -p no:logging      # 82 tests, no network or key needed
.venv/Scripts/python -m uvicorn aegis.main:app --port 8000
.venv/Scripts/python scripts/eval_live.py              # real-model eval against a running backend

# frontend (from frontend/)
npm run build && npm start      # :3000, proxies /api/* to BACKEND_URL
npx tsc --noEmit && npm run lint
```

## Rules

- Evidence excerpts must stay verbatim (grounding + highlighting). Use `validate.prose()` only on
  model-written prose.
- Every LLM stage wraps email content with `wrap_untrusted()` and validates output; model output never
  decides authorization.
- Any URL fetch goes through `pipeline/sandbox.py` (IP pinning, per-hop checks). Never add a direct fetch.
- Keep secrets server-side: the browser talks only to the Next.js proxy.
- No em or en dashes in code, comments, docs or UI copy.
- On Windows, run uvicorn without `--reload` when testing vision (the reloader can leave a stale process).
- `frontend/AGENTS.md`: this Next.js version has breaking changes; read `node_modules/next/dist/docs/`.
