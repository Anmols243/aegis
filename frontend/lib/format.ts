import type { Label, Severity } from "@/lib/api"

export const LABEL_META: Record<Label, { text: string; short: string; color: string; tw: string; ring: string; plain: string }> = {
  SCAM: {
    text: "Scam",
    short: "SCAM",
    color: "var(--aegis-scam)",
    tw: "text-scam",
    ring: "border-scam/45 bg-scam/10 text-scam",
    plain: "This message is a scam. Do not click, reply, or pay.",
  },
  SUSPICIOUS: {
    text: "Suspicious",
    short: "SUSPICIOUS",
    color: "var(--aegis-susp)",
    tw: "text-susp",
    ring: "border-susp/45 bg-susp/10 text-susp",
    plain: "Something is off. Verify through an official channel before acting.",
  },
  LIKELY_SAFE: {
    text: "Likely safe",
    short: "LIKELY SAFE",
    color: "var(--aegis-safe)",
    tw: "text-safe",
    ring: "border-safe/45 bg-safe/10 text-safe",
    plain: "No strong scam signals were found in this message.",
  },
}

export const SEVERITY_TW: Record<Severity, string> = {
  high: "text-scam border-scam/40 bg-scam/10",
  medium: "text-susp border-susp/40 bg-susp/10",
  low: "text-lime border-lime/30 bg-lime/5",
  info: "text-muted-foreground border-hair bg-surface-2",
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "n/a"
  return `${(v * 100).toFixed(digits)}%`
}

export function score100(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "--"
  return String(Math.round(v * 100))
}

export function seconds(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "--"
  return v < 10 ? `${v.toFixed(1)}s` : `${Math.round(v)}s`
}

export function timeAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return ""
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ""
  const s = Math.max(0, Math.round((now - t) / 1000))
  if (s < 45) return "just now"
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  return `${d}d ago`
}

export function prettyKey(s: string): string {
  return s.replace(/[_-]+/g, " ")
}
