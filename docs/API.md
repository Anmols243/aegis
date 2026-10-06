# AEGIS v2 API contract

Base path: `/api/v1`. JSON everywhere except SSE and the screenshot.
The browser never talks to the backend directly: the Next.js app proxies
`/api/*` to the backend and attaches `Authorization: Bearer <AEGIS_API_KEY>`
server-side. The key never reaches the browser.

Auth: when `AEGIS_API_KEY` is set on the backend, every route except
`GET /health`, `GET /share/{token}` and `POST /ingest/agentboxd` (HMAC-signed
instead) requires `Authorization: Bearer <key>`. No CORS by default.

Labels: `SCAM | SUSPICIOUS | LIKELY_SAFE`.
Analysis status: `queued | running | done | failed`.
Stage status: `pending | running | done | failed | skipped`.
Severity: `high | medium | low | info`.

## Objects

### AnalysisSummary
```json
{"id": "a_9f2c1b7e", "created_at": "2026-10-06T08:00:00Z", "source": "web",
 "status": "done", "subject": "Verify your account", "sender": "PayPal <x@paypa1-secure.com>",
 "label": "SCAM", "score": 0.82, "confidence": 0.64, "duration_s": 18.2}
```
`source`: `web | webhook | poller | redteam | sample`. `label/score/confidence` null until done.

### Analysis (detail)
```json
{
  ...AnalysisSummary,
  "error": null,
  "summary": "Two plain-language sentences from the forensic analyst.",
  "email": {"subject": "", "from": "", "reply_to": "", "to": "", "date": "",
            "text": "full plain-text body", "html_available": true,
            "attachments": ["invoice.pdf.exe"]},
  "verdict": {"label": "SCAM", "score": 0.82, "confidence": 0.64,
              "contributions": {"forensic": 0.41, "signals": 0.18},
              "dissent": ["agents disagree: forensic=0.97 vs sandbox=0.30"],
              "strongest": ["forensic", "signals"], "weakest": ["sandbox"],
              "agreement": "majority", "evidence_completeness": 0.75,
              "corroboration": ["forensic analyst: risk 0.97", "deterministic signal: brand-impersonation"]},
  "red_flags": [{"title": "Lookalike domain", "evidence": "paypa1-secure.com",
                 "source": "forensic|signal|vision|sandbox", "severity": "high"}],
  "findings": [{"claim": "", "severity": "high", "artifact": "url", "excerpt": "exact quote from the email"}],
  "signals": [{"name": "brand-impersonation", "severity": "high", "detail": "", "evidence": ""}],
  "techniques": ["lookalike-domain", "urgency-pressure"],
  "triage": {"sender": "", "reply_to": "", "urls": [], "domains": [], "phone_numbers": [],
             "attachment_names": [], "urgency_signals": [], "requested_action": "",
             "language": "en", "brand_mentions": [], "degraded": false},
  "vision": {"impersonated_brand": "PayPal", "confidence": 0.9, "notable_regions": [],
             "reason": "", "screenshot_url": "/api/v1/analyses/a_9f2c1b7e/screenshot"},
  "sandbox": [{"url": "", "final_url": "", "kind": "credential-harvest|malware-drop|benign|unreachable|blocked",
               "status_code": 200, "redirect_chain": [], "page_title": "", "has_password_form": false,
               "has_login_form": false, "download_detected": false, "failure_reason": "", "risk": 0.3}],
  "campaign": {"campaign_id": "c_1", "note": "Linked to 3 earlier emails ...",
               "related": [{"analysis_id": "", "subject": "", "label": "SCAM",
                            "strength": "high|medium|weak", "why": "shares domain + phone",
                            "shared": ["domain:paypa1-secure.com"]}]},
  "actions": ["Do not click any link ..."],
  "stages": [{"name": "triage", "status": "done", "started_at": "", "duration_s": 3.1,
              "summary": "12 entities extracted", "error": null}],
  "share_token": "s_x8Kq...",
  "card_markdown": "verdict card as sent by email"
}
```
`vision` / `campaign.campaign_id` may be null. Stage names, in pipeline order:
`parse, triage, signals, forensic, vision, sandbox, graph, arbiter, report`.

## Endpoints

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/health` | | `{"ok": true, "version": "2.0.0", "llm": true, "agentboxd": true, "vision": true}` |
| GET | `/config/public` | | `{"inbox_address": "zesty-willow-3025@homingbox.net" or null, "features": {"vision": true, "inbox": true}}` |
| POST | `/analyses` | JSON `{"raw": "<pasted email or full .eml source>"}` or multipart `file` (.eml/.txt, max 2 MB) | `202 {"id": "...", "status": "queued"}` |
| GET | `/analyses` | `?limit=50&cursor=<id>&label=SCAM&q=text` | `{"items": [AnalysisSummary], "next_cursor": null}` |
| GET | `/analyses/{id}` | | `Analysis` |
| GET | `/analyses/{id}/events` | SSE | see below |
| GET | `/analyses/{id}/screenshot` | | `image/png` (404 if none) |
| GET | `/analyses/{id}/abuse-report` | | `{"markdown": "..."}` |
| GET | `/share/{token}` | public | `Analysis` minus `email.text`, `triage`, `card_markdown` |
| GET | `/stats` | | `{"total": 0, "by_label": {"SCAM": 0}, "last_24h": 0, "avg_duration_s": 0, "top_techniques": [{"name": "", "count": 0}], "top_brands": [{"name": "", "count": 0}], "campaigns": 0}` |
| GET | `/campaigns` | | `{"campaigns": [{"id": "c_1", "analyses": [{"id": "", "subject": "", "label": ""}], "infra": [{"kind": "domain", "value": ""}], "explanation": ""}], "graph": {"nodes": [{"id": "a:<analysis id>" or "domain:x", "kind": "analysis|sender|domain|url|phone|template", "label": "", "verdict": "SCAM or null"}], "links": [{"source": "", "target": ""}]}}` |
| GET | `/samples` | | `[{"id": "paypal-phish", "title": "", "description": "", "expected": "SCAM", "raw": "..."}]` |
| POST | `/redteam/runs` | `{"sample_id": "paypal-phish"}` or `{"raw": "..."}`, `"n": 1-8`, optional `"seed"` | `202 {"id": "rt_..."}` |
| GET | `/redteam/runs` | | `[{"id": "", "created_at": "", "status": "", "summary": {...}}]` |
| GET | `/redteam/runs/{id}` | | `{"id": "", "created_at": "", "status": "running|done", "seed": 1, "base_subject": "", "variants": [{"index": 0, "axes": ["homoglyph-brand"], "text": "", "analysis_id": "", "status": "queued", "label": null, "score": null, "caught": null}], "summary": {"total": 5, "caught": 3, "missed": 1, "pending": 1}}` |
| GET | `/redteam/summary` | | `{"runs": 0, "variants": 0, "caught": 0, "missed": 0, "by_axis": {"homoglyph-brand": {"total": 0, "missed": 0}}}` |
| POST | `/ingest/agentboxd` | AgentBoxD webhook, header `X-Mailroom-Signature` (HMAC-SHA256 hex) | `202 {"ok": true, "id": "..."}` or `{"ok": true, "duplicate": true}` |

Errors: `{"detail": "message"}` with 400/401/404/413/422/429.
`caught` = variant reached `SCAM` (the expected label for every mutated scam).

## Privacy and viewers (v2.1)

- The Next.js proxy gives every browser an opaque random **viewer token** in an
  `HttpOnly; SameSite=Lax` cookie (`aegis_viewer`, no other cookies, no analytics) and forwards it
  to the backend as `X-Aegis-Viewer`. The proxy ignores any `X-Aegis-Viewer` header sent by the
  browser itself. The backend stores only a SHA-256 hash of it.
- Every analysis has `visibility`: `public` (built-in samples, red team) or `private` (pasted,
  uploaded, mailbox, inbox-forwarded mail). Private analyses are **unlisted**: never in the public
  feed, campaign graph or anyone else's related-email list; reachable by their unguessable id or
  share link, and listed only for the viewer who submitted them.
- `campaign.related` entries the current viewer may not see are returned as
  `{"private": true, "strength": "high", "why": "shares domain + url"}` with no id, subject or values.
- `AnalysisSummary` and `Analysis` gain `"visibility": "public|private"`, `"mine": true|false`,
  `"mailbox_id": "mb_..." or null`, and (once retention ran) `"purged": true`.
- `GET /analyses` gains `?mine=true` (only the caller's own analyses).
- `GET /campaigns` returns only visible members; each campaign gains `"hidden_count": 2`.

## Mailboxes (v2.1)

Connect a mailbox over IMAP with an app password. AEGIS scans **new mail only** (from the moment
of connecting), never marks mail as read, and only adds labels/flags: `AEGIS/Scam`,
`AEGIS/Suspicious` (Gmail labels) or IMAP flags (`\Flagged` + `$AEGIS_Scam` / `$AEGIS_Suspicious`)
elsewhere. It never moves, deletes or sends mail. The owner's own address is replaced with
`[your address]` before analysis. Bodies are purged after `retention_days` (default 7).

### Mailbox
```json
{"id": "mb_...", "provider": "gmail", "email": "me@gmail.com", "host": "imap.gmail.com",
 "status": "active|paused|error", "last_checked_at": "...", "last_error": null,
 "created_at": "...", "scanned": 12, "flagged": 3, "label_mode": "gmail-labels|imap-flags",
 "retention_days": 7}
```

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/oauth/google/start` | `{"retention_days": 1\|7\|30}` | `{"url", "state", "pair"}`: open `url` in a new tab, show `pair`. 503 when Google is not configured, 403 without a viewer |
| GET | `/oauth/google/status?state=` | | Starting viewer only (else 404): `{"status": "pending\|exchanging\|confirm\|saving\|connected\|cancelled\|error\|expired", "email", "error"}` |
| GET | `/oauth/google/callback` | Google's `code`, `state` or `error` | 303 to `/inbox?google=connected` (same browser), `/connect/google?state=` (other browser), or `/inbox?google_error=<message>` |
| GET | `/oauth/google/pairing?state=` | | `{"status", "email", "pair", "error"}` for the confirmation page; 404 when not waiting |
| POST | `/oauth/google/confirm` | `{"state", "connect": true\|false}` | `{"status": "connected", "email"}` (attached to the starting viewer) or `{"status": "cancelled"}` (token revoked); 409 when not waiting |
| GET | `/mailbox-providers` | | First entry `{"id": "google", "oauth": true, "supported": <configured>}`, then `[{"id": "gmail", "name": "Gmail", "host": "imap.gmail.com", "port": 993, "app_password_url": "...", "steps": ["..."], "supported": true}]` (outlook listed with `supported: false` and a reason) |
| POST | `/mailboxes` | `{"provider": "gmail", "email": "...", "app_password": "...", "host": "only for custom", "retention_days": 7}` | `201 Mailbox`; 400 with a readable `detail` if login fails; 403 without a viewer |
| GET | `/mailboxes` | | `[Mailbox]` (this viewer's only) |
| POST | `/mailboxes/{id}/check` | | `202` poll now |
| POST | `/mailboxes/{id}/pause` / `/resume` | | `Mailbox` |
| DELETE | `/mailboxes/{id}` | `?purge=true` also deletes every analysis from it | `204` |

Credentials are encrypted at rest (AES-256-GCM) and never returned. A custom host must resolve
to a public address and use port 993 (implicit TLS); the connection is pinned to the checked IP.

## SSE: `GET /analyses/{id}/events`

Replays everything recorded so far, then streams live until the analysis finishes.

```
event: stage
data: {"name": "forensic", "status": "running", "started_at": "..."}

event: stage
data: {"name": "forensic", "status": "done", "duration_s": 14.2, "summary": "5 grounded findings, risk 0.97"}

event: done
data: {"id": "...", "status": "done", "label": "SCAM", "score": 0.82}
```
After `done` (or `status: failed` in `done`), fetch `/analyses/{id}` for the full object.
A `: ping` comment is sent every 15 s.
