"use client"

import * as React from "react"
import { AlertTriangle, Inbox, Loader2 } from "lucide-react"

import type { Label, Severity } from "@/lib/api"
import { LABEL_META, SEVERITY_TW } from "@/lib/format"
import { cn } from "@/lib/utils"

export function VerdictBadge({ label, className, size = "sm" }: { label: Label | null; className?: string; size?: "sm" | "lg" }) {
  if (!label) {
    return (
      <span className={cn("inline-flex items-center rounded-full border border-hair px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground", className)}>
        pending
      </span>
    )
  }
  const m = LABEL_META[label]
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border font-mono font-semibold uppercase",
        size === "lg" ? "px-4 py-1.5 text-xs tracking-[0.18em]" : "px-2.5 py-1 text-[10px] tracking-[0.14em]",
        m.ring,
        className,
      )}
    >
      {m.short}
    </span>
  )
}

export function SeverityPill({ severity }: { severity: Severity }) {
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em]", SEVERITY_TW[severity])}>
      {severity}
    </span>
  )
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
      <Loader2 className="size-4 animate-spin text-lime" aria-hidden="true" />
      <span className="label-mono">{label}</span>
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <Inbox className="size-6 text-faint" aria-hidden="true" />
      <p className="label-mono text-[12px] text-muted-foreground">{title}</p>
      {children ? <div className="max-w-md text-sm text-faint">{children}</div> : null}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-scam/30 bg-scam/5 px-6 py-10 text-center">
      <AlertTriangle className="size-5 text-scam" aria-hidden="true" />
      <p className="text-sm text-ink">{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="chip">
          Try again
        </button>
      ) : null}
    </div>
  )
}

/** Semicircle score gauge, 0..1. */
export function ScoreGauge({ score, label, size = 180 }: { score: number | null; label: Label | null; size?: number }) {
  const v = Math.max(0, Math.min(1, score ?? 0))
  const color = label ? LABEL_META[label].color : "var(--aegis-muted)"
  const r = 70
  const len = Math.PI * r
  return (
    <div className="relative" style={{ width: size, height: size * 0.62 }}>
      <svg viewBox="0 0 180 112" className="h-full w-full" role="img" aria-label={`Risk score ${Math.round(v * 100)} out of 100`}>
        <path d="M20 96 A70 70 0 0 1 160 96" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="12" strokeLinecap="round" />
        <path
          d="M20 96 A70 70 0 0 1 160 96"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${len * v} ${len}`}
          style={{ transition: "stroke-dasharray 0.9s cubic-bezier(.2,.7,.2,1)", filter: `drop-shadow(0 0 8px ${color})` }}
        />
        <line x1="62" y1="35" x2="58" y2="27" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />
        <line x1="128" y1="44" x2="134" y2="37" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />
      </svg>
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="font-mono text-4xl font-semibold tabular-nums text-ink">{score === null ? "--" : Math.round(v * 100)}</span>
        <span className="label-mono">risk score</span>
      </div>
    </div>
  )
}

export function SectionTitle({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <h2 className="label-mono text-[11px] text-ink/80">{children}</h2>
      <span className="h-px flex-1 bg-hair" />
      {aside}
    </div>
  )
}
