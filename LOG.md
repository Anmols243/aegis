# Log

Newest first.

## 2026-10-08: Campaign operator map replaces the force graph

- **Changed:** `campaigns-view.tsx`: the force-directed graph (random layout, overlapping labels) is
  replaced by a fixed three-column operator map: emails (deduped, wrap to 2 lines, open their case),
  an operator hub, and shared infrastructure grouped by type with coverage (`4/4` = in 4 of 4
  emails). SVG connectors are measured from the rendered rows; hovering or focusing a row lights
  its connectors (moving dashes, `.aegis-flow` in `globals.css`, off under reduced motion) and dims
  rows it does not touch. The separate infrastructure and linked-email lists and the "All
  campaigns" toggle are gone (the map and the campaign list cover them). Below `md` the columns
  stack without connectors. `components/aegis/force-graph.tsx` deleted.
- **Note:** `react-force-graph-2d` is no longer imported anywhere but is still in `package.json`.
- **Verified:** tsc, eslint, build. Screenshots at 1440px (apple and gmail-sender campaigns, hover
  on the sender row lights its path and dims the template) and 390px (stacked, scrollWidth 390).

## 2026-10-08: Campaigns page redesign, duplicate campaign ids, test data cleanup

- **Fixed:** duplicate React key on /campaigns. Campaign ids were `c_` + the first 8 chars of the
  earliest member id, which is a millisecond timestamp, so campaigns seeded within ~4s collided.
  Now `c_` + 10 hex of SHA-256 of the full id (`services/campaigns.py`). Regression test
  `test_campaign_ids_unique_for_close_submissions` fails on the old code, passes now (83 tests).
- **Changed:** /campaigns rebuilt (`components/aegis/campaigns-view.tsx`): stat strip, sticky campaign
  list named by operator (sender domain, else address, domain, link, phone) with verdict bar and
  indicator icons, detail pane with first/last seen, a graph focused on the selected campaign
  (zoom-to-fit, capped at 2x, "All campaigns" toggle dims the others), deduped linked emails and
  infrastructure grouped by type. New `components/aegis/force-graph.tsx` wrapper passes the graph ref
  through `next/dynamic` and sets link distance and charge range.
- **API:** campaign `analyses[]` gain `created_at`; graph nodes document the existing `campaign` field
  (docs/API.md, lib/api.ts).
- **Data:** deleted the 28 manually pasted (`source='web'`) analyses from the local
  `backend/data/aegis.db` with their stage runs and entities (user request). Backup kept outside the
  repo in the session scratchpad.
- **Also:** AgentBoxD key checked read-only: valid, inbox `zesty-willow-3025@homingbox.net` active.
  Not wired: `backend/.env` does not exist yet (user to create it).
- **Verified:** pytest 83 passed, tsc, eslint, build. Screenshots at 1440px (focus and all-campaigns
  graphs, settled) and 390px (no horizontal scroll). The browser console was not checked for the
  key warning (prod build); uniqueness is covered by the test.

## 2026-10-07: HUD corner marks follow the rounded corners

- **Changed:** `app/globals.css` `.hud::before`: the corner marks were square L-brackets (gradient
  strokes) and clashed with the rounded panel corners. They are now a 1px rounded ring 8px inside
  the border with radius `--hud-r - 8px` (concentric), masked to 20px at each corner. `.hud`
  takes its radius from `--hud-r`; the two 24px panels (home red-team panel, verdict report) use
  `[--hud-r:1.5rem]` instead of `rounded-3xl` / `rounded-[1.5rem]`.
- **Verified:** build; computed panel radius 24px and mark radius 16px on the red-team panel,
  `mask-composite: intersect` applied; home screenshot shows curved marks on every panel corner.
  Hover (`.hud-interactive`) recolors through `--m` (by code, not checked in browser).

## 2026-10-07: Background still choppy, follow-up

- **Changed:** `liquid-metal.tsx`: 30 fps cap removed (draws every display frame again); new
  `intensity` prop mixes the chrome toward `#0a0c0e` in the shader. `AppBackground` passes
  `intensity={0.45}` instead of the CSS `opacity-45` class.
- **Why:** The cap made the flow step every 2nd frame at 60 Hz and unevenly (4 or 5 frames) at
  144 Hz, which reads as stutter; the half-res shader costs ~0.6 ms so it can run every frame.
  CSS opacity added a full-screen layer blend per frame.
- **Verified:** tsc, eslint, build. No long tasks on / or /analyze during a scroll. Canvas
  720x450, wrapper opacity 1, screenshot matches the previous look. Smoothness on a real display
  not measured.

## 2026-10-07: Background performance (lag and low fps)

- **Changed:** `.hud` lost `backdrop-filter: blur(6px)` (`app/globals.css`); site nav lost
  `backdrop-blur-xl`, fill raised from 0.78 to 0.92. `liquid-metal.tsx` renders at half CSS
  resolution (`RENDER_SCALE`) and caps drawing at 30 fps (`FRAME_MS`).
- **Why:** With an animated background every backdrop-filter region (35 `.hud` uses plus the
  nav) is re-blurred every frame; with the old static dots it was blurred once. Panels are 82%
  opaque, so the blur was barely visible.
- **Verified:** tsc, eslint, build. Shader benchmark in headless Chrome, 20 draws each: 1.1 ms
  at 1440x900, 0.6 ms at 720x450 (so the shader alone was not the main cost here). On /analyze:
  canvas 720x450 for a 1440x900 viewport, zero elements with a backdrop filter, screenshot
  unchanged in look. Real-GPU frame rate not measured; headless rAF is not display-bound.

## 2026-10-07: Liquid metal background replaces the animated gradient

- **Changed:** new `frontend/components/ui/liquid-metal.tsx`, a port of the educalvolpz
  "liquid-metal" WebGL2 shader from 21st.dev, chrome palette only, pointer input removed (no
  listeners, no `uPointer`). `AppBackground` renders it at 45% opacity under the vignette.
  `components/ui/animated-gradient.tsx` deleted (no other users). `brand.md` updated.
- **Why:** User asked for this background across the site, not reacting to the mouse.
- **Verified:** `tsc --noEmit`, eslint, `npm run build`. WebGL2 canvas at 1440x900; two
  screenshots 2s apart differ (animating). Screenshots of / and /analyze: copy and panels
  readable. 25% opacity was tried first and the chrome texture was barely visible.

## 2026-10-07: Animated gradient background

- **Changed:** new `frontend/components/ui/animated-gradient.tsx`, a port of the componentry
  "animated-gradient" WebGL2 shader from 21st.dev (Edge shape, Aurora preset parameters, AEGIS
  colors `#0a0c0e` / `#121a08` / `#d9ff3d`). `AppBackground` renders it at 25% opacity under the
  existing vignette, replacing the dot pattern. `brand.md` updated (it still named `SonarGrid`).
- **Why:** User asked for that background, whole site, brand lime, toned down.
- **Notes:** Renders at 1x pixel ratio to keep the full-screen shader cheap. Reduced motion draws
  one still frame; no WebGL2 leaves the plain page background.
- **Verified:** `tsc --noEmit`, eslint, `npm run build`. Canvas present with a WebGL2 context at
  1440x900. Screenshots of /, /analyze (1440px) and / (390px): hero copy and panels readable.
  40% opacity was tried first and washed out the hero body text.

## 2026-10-07: Border beam turns corners smoothly

- **Changed:** `frontend/components/ui/border-beam.tsx` rewritten. The streak is now six stacked
  dashes on an SVG rounded-rect stroke (sized by `ResizeObserver`), driven by one `motion` value,
  instead of a 90px square riding `offset-path` with auto-rotate under a ring mask. Props unchanged.
- **Why:** At each rounded corner the square spun 90 degrees over a ~30px arc, so the masked slice
  jumped (visible jitter). A dash follows the curve exactly with no rotation.
- **Verified:** `tsc --noEmit`, eslint, `npm run build`. On /analyze, sampled the head dash offset
  over 120 frames: monotonic, no stalled frames. Screenshot caught the streak mid-corner, following
  the curve. Applies to all three users (analyze form, red team, verdict report).
- **Follow-up:** the streak restarted at the top-left corner (the path start) because the dash
  pattern period was dash + perimeter, so the tail could not wrap. Gap is now perimeter - dash.
  Verified by freezing a dash 30px past the start: one unbroken streak from the left edge, round
  the corner, onto the top edge.

## 2026-10-07: Analyze form border beam stays on the panel

- **Changed:** `frontend/components/aegis/analyze-form.tsx`, `self-start` on the form's `BorderBeam`.
- **Why:** As a grid item the beam wrapper stretched to the taller samples column, so the streak
  traced an invisible box below the form panel.
- **Verified:** `npm run build`; at 1440px the wrapper and form bounds now match (277 to 773 px,
  row 277 to 953) and a screenshot shows the streak on the panel edge.

## 2026-10-07: Docs for Google + Microsoft sign-in

- **Changed:** README (features, privacy bullets, env table with `MICROSOFT_*`, Microsoft setup
  steps, limits), ARCHITECTURE (providers, mailboxes and sign-in sections), docs/API.md (generic
  `/oauth/{provider}/*` routes, `/oauth/status`, `/oauth/pairing`, `/oauth/confirm`, Mailbox shape
  with `manage_url`, `POST /mailboxes` removed), DECISIONS D11, privacy page delete wording,
  CLAUDE.md test count (84 to 82).
- **Why:** The docs still described IMAP and app passwords and Google-only route names after
  commit `894acab`.
- **Verified:** Every route, status, scope, label mode and error path in the docs checked against
  `api/routes.py`, `services/mailboxes.py` and `providers/{oauth,google,microsoft}.py`. 82 backend
  tests pass. No code changed apart from one sentence of UI copy.

## 2026-10-06: Sign in with Microsoft, IMAP removed

- **Changed:** `providers/oauth.py` (shared PKCE flow), `providers/microsoft.py` (Graph: new mail by
  received time, categories + flag), generic `/oauth/{provider}/*` routes and `/connect?state=`;
  `providers/imap.py` and `POST /mailboxes` deleted; DotPattern site background. See D11.
- **Why:** Google and Microsoft cover most users with no passwords; Yahoo and iCloud have no usable
  mail sign-in for apps.
- **Verified:** 82 backend tests (7 in `test_oauth.py` with fake Google and Graph); mutation check
  18/18 caught.
- **Not verified:** Microsoft flow in a browser, the dot background in a browser, any real account.

## 2026-10-06: Sign in with Google for Gmail

- **Changed:** `providers/google.py` (OAuth + PKCE, Gmail history polling, labels, revoke),
  `/oauth/google/start` and `/oauth/google/callback`, Google-first connect form on `/inbox` with app
  passwords behind a toggle, privacy copy. See DECISIONS.md D10.
- **Why:** Google refused to show app passwords for a teammate's account; app passwords were too much
  friction.
- **Verified:** 82 backend tests pass (fake Google API: state bound to browser and single use, PKCE,
  scope check, new-mail-only cursor, sent mail skipped, label + star, encrypted token, revoke on
  disconnect). Mutation check: breaking each of those 7 guards fails a test. Browser: button opens
  accounts.google.com with the right parameters; cancel returns to `/inbox` with a toast.
- **Not verified:** a full consent with a real OAuth client (needs the Google Cloud setup in README).
- **Follow-up:** sign-in from an app's built-in browser. Google opens in a new tab; if it returns to
  another browser, `/connect/google` asks to confirm a 4-digit code shown in both windows, and the
  starting window updates by polling. 84 tests; mutation check: 10 guards, all caught. Browser: two
  isolated sessions against a fake Google showed matching codes, the confirm page, the panel
  connecting by itself and the other browser getting nothing; disconnect cleaned up.

## 2026-10-06: Mailbox connection and privacy (v2.1)

- **Changed:** Connect an IMAP mailbox (Gmail, Yahoo, iCloud, custom) with an app password; new mail
  is analyzed and tagged `AEGIS/Scam` or `AEGIS/Suspicious`. Privacy model: per-browser viewer cookie,
  private-by-default analyses, anonymised cross-user relations, AES-256-GCM credentials, owner
  address redaction, retention purge, disconnect-and-delete. See DECISIONS.md D8, D9.
- **Verified:** 78 backend tests pass (fake IMAP server for connect, poll, label, disconnect;
  visibility, redaction, retention, encryption). Mutation check: disabling private-list filtering,
  related redaction, owner redaction, the mailbox owner check or the purge each fails a test.
  Live backend migrated the existing database in place.
- **Not verified:** a real Gmail/Yahoo/iCloud mailbox (needs a test account and app password).
## 2026-10-06: v2 rewrite (branch `overhaul`)

- **Changed:** New `backend/` (FastAPI async, SQLite queue, DAG pipeline with SSE progress, Featherless
  provider, AgentBoxD webhook + poller) and `frontend/` (Next.js: landing, analyze, live case view with
  highlighted evidence, cases feed, campaign graph, red-team arena, share page). v1 moved to `legacy/v1/`.
  New: BEC checks, corroboration rule, hardened SSRF sandbox, API-key auth, streaming body limits,
  rate limits, share links, abuse reports, built-in samples, live eval script.
- **Why:** The v1 security review (open CORS on an unauthenticated API, SSRF bypasses, late body-size
  check) and a full overhaul requested for the hackathon submission. See DECISIONS.md D1 to D7.
- **Verified:** 70 backend tests pass (SSRF against a local server, webhook HMAC + idempotency, auth,
  limits, API end to end with a fake model). Live eval with real models: 22/22 correct, 0 false
  positives, 15 s mean (eval/RESULTS.md). Frontend `npm run build`, `tsc` and lint clean; every page
  screenshot-checked at 1440 and 390 px against the live backend; `.eml` upload through the proxy
  gave SCAM on a Netflix lookalike.
- **Not verified:** live AgentBoxD webhook and auto-reply in v2; Docker image build.

## 2026-10-06: v1 dashboard tweaks (before the rewrite)

- Sonar-grid background, HUD panels, border beam, dot pattern, filter chip contrast, scroll-bar
  clipping, `/sonar-grid.js` rate-limit exemption. Superseded by the v2 frontend.
