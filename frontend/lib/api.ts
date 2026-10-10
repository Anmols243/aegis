// Typed client for the AEGIS v2 API (contract: docs/API.md).
// The browser only ever calls relative /api/v1 paths; the Next.js route
// handler in app/api/[...path] forwards them to the backend server-side.

export type Label = "SCAM" | "SUSPICIOUS" | "LIKELY_SAFE"
export type AnalysisStatus = "queued" | "running" | "done" | "failed"
export type StageStatus = "pending" | "running" | "done" | "failed" | "skipped"
export type Severity = "high" | "medium" | "low" | "info"
export type Source = "web" | "webhook" | "poller" | "redteam" | "sample" | "mailbox"
export type Visibility = "public" | "private"

export const STAGES = [
  "parse",
  "triage",
  "signals",
  "forensic",
  "vision",
  "sandbox",
  "graph",
  "arbiter",
  "report",
] as const
export type StageName = (typeof STAGES)[number]

export interface AnalysisSummary {
  id: string
  created_at: string
  source: Source
  status: AnalysisStatus
  subject: string
  sender: string
  label: Label | null
  score: number | null
  confidence: number | null
  duration_s: number | null
  visibility?: Visibility
  mine?: boolean
  mailbox_id?: string | null
  purged?: boolean
}

export interface EmailInfo {
  subject: string
  from: string
  reply_to: string
  to: string
  date: string
  text?: string
  html_available: boolean
  attachments: string[]
}

export interface Verdict {
  label: Label
  score: number
  confidence: number
  contributions: Record<string, number>
  dissent: string[]
  strongest: string[]
  weakest: string[]
  agreement: string
  evidence_completeness: number
  corroboration: string[]
}

export interface RedFlag {
  title: string
  evidence: string
  source: "forensic" | "signal" | "vision" | "sandbox"
  severity: Severity
}

export interface Finding {
  claim: string
  severity: Severity
  artifact: string
  excerpt: string
}

export interface Signal {
  name: string
  severity: Severity
  detail: string
  evidence: string
}

export interface Triage {
  sender: string
  reply_to: string
  urls: string[]
  domains: string[]
  phone_numbers: string[]
  attachment_names: string[]
  urgency_signals: string[]
  requested_action: string
  language: string
  brand_mentions: string[]
  degraded: boolean
}

export interface Vision {
  impersonated_brand: string | null
  confidence: number
  notable_regions: string[]
  reason: string
  screenshot_url: string | null
}

export type SandboxKind = "credential-harvest" | "malware-drop" | "benign" | "unreachable" | "blocked"

export interface SandboxResult {
  url: string
  final_url: string
  kind: SandboxKind
  status_code: number | null
  redirect_chain: string[]
  page_title: string
  has_password_form: boolean
  has_login_form: boolean
  download_detected: boolean
  failure_reason: string
  risk: number
}

export interface RelatedAnalysis {
  analysis_id?: string | null
  subject?: string
  label?: Label | null
  strength: "high" | "medium" | "weak"
  why: string
  shared?: string[]
  /** True when the related email belongs to someone else: no id, subject or values are returned. */
  private?: boolean
}

export interface CampaignInfo {
  campaign_id: string | null
  note: string
  related: RelatedAnalysis[]
}

export interface Stage {
  name: StageName | string
  status: StageStatus
  started_at?: string | null
  duration_s?: number | null
  summary?: string | null
  error?: string | null
}

export interface Analysis extends AnalysisSummary {
  error: string | null
  summary: string
  email: EmailInfo
  verdict: Verdict | null
  red_flags: RedFlag[]
  findings: Finding[]
  signals: Signal[]
  techniques: string[]
  triage?: Triage | null
  vision: Vision | null
  sandbox: SandboxResult[]
  campaign: CampaignInfo | null
  actions: string[]
  stages: Stage[]
  share_token: string | null
  card_markdown?: string
}

export interface Paged<T> {
  items: T[]
  next_cursor: string | null
}

export interface Health {
  ok: boolean
  version: string
  llm: boolean
  agentboxd: boolean
  vision: boolean
}

export interface PublicConfig {
  inbox_address: string | null
  features: Record<string, boolean>
}

export interface Mailbox {
  id: string
  provider: string
  email: string
  host: string
  status: "active" | "paused" | "error" | string
  last_checked_at: string | null
  last_error: string | null
  created_at: string | null
  scanned: number
  flagged: number
  label_mode: string
  retention_days: number
  manage_url: string | null
}

export interface MailboxProvider {
  id: string
  name: string
  covers: string
  /** False until the server has that provider's OAuth client configured. */
  supported: boolean
}

export interface OAuthStart {
  url: string
  state: string
  pair: string
}

export type SignInState = "pending" | "exchanging" | "confirm" | "saving" | "connected" | "cancelled" | "error" | "expired"

/** Sign-in that returned to a different browser: confirm it matches the starting window's code. */
export interface SignInPairing {
  status: SignInState
  provider: string
  email: string | null
  pair: string
  error?: string | null
}

export interface LiveInboxItem {
  /** Opaque, stable row key (not the analysis id). */
  key: string
  /** The analysis id: the feed lists only this browser's own mail. */
  id: string | null
  created_at: string | null
  status: AnalysisStatus
  label: Label | null
  score: number | null
  duration_s: number | null
  subject: string | null
  /** Masked, e.g. `sh***@gmail.com`. */
  sender: string | null
  /** First words of the body, partially censored. */
  preview: string
  replied: boolean
  private: boolean
  stages: { name: StageName | string; status: StageStatus }[]
}

/** One inbox email dissected for /live: an Analysis, partially censored, with `id` null. */
export type LiveInboxDetail = Analysis & { key: string }

export interface LiveInbox {
  enabled: boolean
  address: string | null
  public: boolean
  /** This browser's personal code; mail whose subject carries it is shown to this browser only. */
  code: string | null
  items: LiveInboxItem[]
}

export interface Stats {
  total: number
  by_label: Partial<Record<Label, number>>
  last_24h: number
  avg_duration_s: number
  top_techniques: { name: string; count: number }[]
  top_brands: { name: string; count: number }[]
  campaigns: number
}

export interface Campaign {
  id: string
  analyses: { id: string; subject: string; label: Label | null; created_at?: string | null }[]
  infra: { kind: string; value: string }[]
  explanation: string
  /** Members the current viewer may not see. */
  hidden_count?: number
}

export interface GraphNode {
  id: string
  kind: "analysis" | "sender" | "domain" | "url" | "phone" | "template" | string
  label: string
  verdict?: Label | null
  /** Id of the campaign this node belongs to. */
  campaign?: string
}

export interface GraphLink {
  source: string
  target: string
}

export interface CampaignsResponse {
  campaigns: Campaign[]
  graph: { nodes: GraphNode[]; links: GraphLink[] }
}

export interface Sample {
  id: string
  title: string
  description: string
  expected: Label
  raw: string
}

export interface RedteamSummaryCounts {
  total: number
  caught: number
  missed: number
  pending: number
}

export interface RedteamVariant {
  index: number
  axes: string[]
  text: string
  analysis_id: string
  status: AnalysisStatus
  label: Label | null
  score: number | null
  caught: boolean | null
}

export interface RedteamRun {
  id: string
  created_at: string
  status: "running" | "done" | string
  seed: number
  base_subject: string
  variants: RedteamVariant[]
  summary: RedteamSummaryCounts
}

export interface RedteamRunListItem {
  id: string
  created_at: string
  status: string
  summary: RedteamSummaryCounts
}

export interface RedteamSummary {
  runs: number
  variants: number
  caught: number
  missed: number
  by_axis: Record<string, { total: number; missed: number }>
}

export interface StageEvent {
  name: string
  status: StageStatus
  started_at?: string
  duration_s?: number
  summary?: string
  error?: string | null
}

export interface DoneEvent {
  id: string
  status: AnalysisStatus
  label?: Label | null
  score?: number | null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE = "/api/v1"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await send(path, init)
  return (await res.json()) as T
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { cache: "no-store", ...init })
  } catch {
    throw new ApiError(0, "Could not reach the AEGIS service.")
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === "string") detail = body.detail
      else if (Array.isArray(body.detail)) detail = "The request was not valid."
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return res
}

function qs(params: Record<string, string | number | null | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ""
}

export const api = {
  health: () => request<Health>("/health"),
  publicConfig: () => request<PublicConfig>("/config/public"),
  inboxLive: () => request<LiveInbox>("/inbox/live"),
  inboxLiveDetail: (key: string) => request<LiveInboxDetail>(`/inbox/live/${encodeURIComponent(key)}`),
  stats: () => request<Stats>("/stats"),
  samples: () => request<Sample[]>("/samples"),

  createAnalysisFromText: (raw: string) =>
    request<{ id: string; status: AnalysisStatus }>("/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw }),
    }),
  createAnalysisFromFile: (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return request<{ id: string; status: AnalysisStatus }>("/analyses", { method: "POST", body: fd })
  },
  listAnalyses: (p: { limit?: number; cursor?: string | null; label?: Label | null; q?: string; mine?: boolean }) =>
    request<Paged<AnalysisSummary>>(
      `/analyses${qs({ limit: p.limit ?? 20, cursor: p.cursor, label: p.label, q: p.q, mine: p.mine ? "true" : null })}`,
    ),
  /** Erase every case this browser analyzed (pasted and emailed). */
  deleteHistory: () => request<{ deleted: number }>("/history", { method: "DELETE" }),
  analysis: (id: string) => request<Analysis>(`/analyses/${encodeURIComponent(id)}`),
  abuseReport: (id: string) => request<{ markdown: string }>(`/analyses/${encodeURIComponent(id)}/abuse-report`),
  share: (token: string) => request<Analysis>(`/share/${encodeURIComponent(token)}`),
  eventsUrl: (id: string) => `${BASE}/analyses/${encodeURIComponent(id)}/events`,

  mailboxProviders: () => request<MailboxProvider[]>("/mailbox-providers"),
  /** Start Sign in with Google (or Microsoft); open `url` in this tab. */
  startOAuth: (provider: string, retentionDays = 1) =>
    request<OAuthStart>(`/oauth/${encodeURIComponent(provider)}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ retention_days: retentionDays }),
    }),
  signInPairing: (state: string) => request<SignInPairing>(`/oauth/pairing?state=${encodeURIComponent(state)}`),
  signInConfirm: (state: string, connect: boolean) =>
    request<{ status: "connected" | "cancelled"; email?: string }>("/oauth/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state, connect }),
    }),
  listMailboxes: () => request<Mailbox[]>("/mailboxes"),
  checkMailbox: (id: string) => request<{ ok: boolean }>(`/mailboxes/${encodeURIComponent(id)}/check`, { method: "POST" }),
  pauseMailbox: (id: string) => request<Mailbox>(`/mailboxes/${encodeURIComponent(id)}/pause`, { method: "POST" }),
  resumeMailbox: (id: string) => request<Mailbox>(`/mailboxes/${encodeURIComponent(id)}/resume`, { method: "POST" }),
  /** 204, no body. */
  removeMailbox: (id: string, purge = false) =>
    send(`/mailboxes/${encodeURIComponent(id)}?purge=${purge}`, { method: "DELETE" }).then(() => undefined),

  campaigns: () => request<CampaignsResponse>("/campaigns"),

  createRedteamRun: (body: { sample_id?: string; raw?: string; n: number; seed?: number }) =>
    request<{ id: string }>("/redteam/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  redteamRuns: () => request<RedteamRunListItem[]>("/redteam/runs"),
  redteamRun: (id: string) => request<RedteamRun>(`/redteam/runs/${encodeURIComponent(id)}`),
  redteamSummary: () => request<RedteamSummary>("/redteam/summary"),
}
