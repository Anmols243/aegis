# AEGIS frontend

Next.js (App Router) + TypeScript + Tailwind + shadcn/ui. Talks to the AEGIS
backend through a same-origin proxy (`app/api/[...path]/route.ts`), which
attaches the API key server-side. API contract: `../docs/API.md`.

## Run

Settings (environment variables or `.env.local`, server-side only):

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | Where the proxy forwards `/api/*` |
| `AEGIS_API_KEY` | unset | Sent as `Authorization: Bearer` to the backend; never exposed to the browser |

```bash
npm install
npm run dev                  # http://localhost:3000
```

The backend must be running (default `http://127.0.0.1:8000`).

## Build and check

```bash
npm run build && npm start   # production build, serves on :3000
npx tsc --noEmit             # typecheck
npm run lint
```

## Pages

| Route | What it does |
|---|---|
| `/` | Landing: hero, live counters, how the pipeline works |
| `/analyze` | Paste an email, drop an `.eml`, or run a sample |
| `/cases` | Feed of analyses with verdict filters and search |
| `/cases/[id]` | Live agent pipeline (SSE), then the verdict with evidence highlighted in the email |
| `/campaigns` | Interactive threat graph of linked emails |
| `/redteam` | Mutation arena: attack the pipeline, see what gets caught |
| `/share/[token]` | Public read-only verdict page |

Design tokens and component notes: `brand.md`.
