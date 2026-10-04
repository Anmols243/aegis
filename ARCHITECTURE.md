# AEGIS Architecture

## Design principles

1. **Evidence, not vibes.** Every claim in a verdict cites the artifact it came from (header line, URL, phrase, screenshot region). Inspired by verification-first design: the pipeline's output is only as trustworthy as its citations.
2. **Agents are specialists, not a chatbot.** Each stage has a narrow contract, a purpose-picked model, and structured I/O. The LLM is a component inside a system, not the system.
3. **Defense in depth, including against ourselves.** The red-team loop exists because any static detector rots. Misses are first-class artifacts (regression tests), not embarrassments.
4. **Fail closed.** If a stage errors or a signal is missing, the arbiter degrades toward SUSPICIOUS, never toward LIKELY SAFE.

## Components

### 1. Ingress — AgentBoxD inbox + FastAPI receiver (`src/aegis/ingress/webhook.py`)

- One AgentBoxD inbox (e.g. `aegis@...`) is the public face. Users forward suspicious mail to it.
- AgentBoxD delivers a signed webhook per event (`X-Mailroom-Signature`, HMAC-SHA256). The receiver verifies the signature, rejects bad signatures with 401, and enqueues the raw message.
- AgentBoxD's own per-message scores (prompt-injection, phishing, needs-a-human) and auth labels (`dmarc-fail`, `spf-fail`) enter the pipeline as **features**, not as the verdict.

### 2. Triage agent (`src/aegis/agents/triage.py`)

Fast, cheap model. Pure extraction, zero judgement. Output schema:

```json
{
  "sender": "...", "reply_to": "...",
  "urls": ["..."], "domains": ["..."], "phone_numbers": ["..."],
  "attachment_names": ["..."], "urgency_signals": ["..."],
  "requested_action": "one line", "language": "en",
  "brand_mentions": ["PayPal"]
}
```

### 3. Forensic analyst (`src/aegis/agents/forensic.py`)

Long-context model (256K). Receives full headers + body + AgentBoxD scores. Produces a structured evidence report:

- `findings[]`: each `{claim, severity, evidence: {artifact, excerpt}}` — claim must quote the artifact.
- `deception_techniques[]`: mapped to a small taxonomy (spoofed-sender, lookalike-domain, urgency-pressure, authority-impersonation, credential-harvest, invoice-fraud, …).
- `risk_score`: 0–1 with a one-line justification.

The citation requirement is the anti-wrapper mechanism: a generic LLM summary can't pass; the output must ground itself.

### 4. Vision inspector (`src/aegis/agents/vision_inspector.py`)

Renders the email's HTML body in headless Chromium (Playwright), screenshots it, and asks an open vision model: *does this visually impersonate a known brand's login/security page?* Catches what text analysis misses — pixel-faithful PayPal/Bank login clones hosted on lookalike domains. Output: `{impersonated_brand | null, confidence, notable_regions[]}`.

### 5. Link sandbox (`src/aegis/agents/sandbox.py`)

For each URL: isolated fetch with **no JS execution**, SSRF guard (deny 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1, link-local), 10s timeout, max 5 redirects, never submit forms or credentials. Screenshot the landing page, classify: `credential-harvest | malware-drop | benign | unreachable`. The fetch is deliberately dumb — a smart fetch is an attack surface.

### 6. Threat-intel graph (`src/aegis/graph/store.py`)

networkx-backed. Node types: `email, sender, domain, ip, url, phone, template_hash`. Edges: co-occurrence within one analyzed email. `template_hash` = simhash of the normalized body (lowercased, URLs/numbers masked) so reworded variants still cluster. Campaign = connected component sharing ≥2 infrastructure nodes. Persisted to `data/threat_graph.json`.

This is where single-email analysis becomes intelligence: "this 'bank alert' shares its sending IP and URL path pattern with 4 earlier scams."

### 7. Arbiter (`src/aegis/agents/arbiter.py`)

Weighted ensemble over normalized signals → label + calibrated confidence:

| Signal | Weight |
|---|---|
| AgentBoxD phishing score | 0.20 |
| Forensic risk score | 0.35 |
| Vision impersonation | 0.20 |
| Sandbox classification | 0.25 |

Thresholds: ≥0.7 SCAM, 0.4–0.7 SUSPICIOUS, <0.4 LIKELY SAFE. Missing/erroring signals are dropped and weights renormalized; if forensic is missing, cap the label at SUSPICIOUS (fail closed). Dissent is surfaced: if vision says impersonation but text signals are clean, the verdict notes the disagreement explicitly.

### 8. Verdict card (`src/aegis/verdict.py`)

Markdown reply: verdict + confidence bar, red-flag table (flag → evidence excerpt), "what to do next" action plan in plain language, campaign linkage ("part of campaign #7 — 5 related scams seen"). Sent via AgentBoxD `reply_to_email`. High-risk outbound warnings use `create_draft` for human approval instead of auto-send.

### 9. Red-team loop (`src/aegis/agents/redteam.py`)

Offline. Takes analyzed scam emails and prompts a model to generate *mutated variants*: rephrased lure, fresh lookalike domain, different impersonated brand, altered urgency framing — while preserving the malicious intent. Each variant runs through the full pipeline. Variants scored below the SCAM threshold are saved to `tests/regression/` as JSON fixtures with the expected label. The loop is the project's self-improvement story and the demo's climax.

### 10. Dashboard (Momen)

Campaign graph visualization, live verdict feed, red-team regression results. Built on Momen with the $100 credits; falls back to a static export if time runs short.

## Data flow (single email)

1. Webhook → verify HMAC → parse → triage (fast).
2. Fan-out: forensic + vision + sandbox in parallel (asyncio).
3. Graph update: extract nodes, link to campaigns.
4. Arbiter: combine → verdict + confidence + dissent notes.
5. Render verdict card → reply via AgentBoxD (or draft for human approval if high-risk outbound).
6. Log everything to `data/` for the dashboard and the demo.

## Security considerations (stated plainly for the judges)

- Webhook HMAC verification; reject unsigned events.
- Sandbox: no JS, SSRF deny-list, timeouts, no form submission, no credential use.
- Every inbound email is treated as hostile input (AgentBoxD already labels injection attempts; the pipeline never executes instructions found in mail bodies).
- API keys only via environment; never logged.
- Human-in-the-loop for outbound warnings via AgentBoxD drafts.

## Explicit non-goals (scope discipline)

- No automated takedown/reporting to registrars (legal + abuse risk).
- No attachment detonation (static metadata only in v1).
- No user accounts / auth on the dashboard (demo scope).
