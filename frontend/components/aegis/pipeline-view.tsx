"use client"

import { Check, Eye, FileSearch, Fingerprint, Gavel, Globe, Loader2, Minus, Network, ScanText, ShieldCheck, Sparkles, X } from "lucide-react"

import { STAGES, type Stage } from "@/lib/api"
import { seconds } from "@/lib/format"
import { cn } from "@/lib/utils"

const ICONS = {
  parse: ScanText,
  triage: Sparkles,
  signals: Fingerprint,
  forensic: FileSearch,
  vision: Eye,
  sandbox: Globe,
  graph: Network,
  arbiter: Gavel,
  report: ShieldCheck,
} as const

const ROLE: Record<string, string> = {
  parse: "Read the message",
  triage: "Extract entities",
  signals: "Deterministic checks",
  forensic: "Evidence analyst",
  vision: "Brand look-alike",
  sandbox: "Link detonation",
  graph: "Campaign links",
  arbiter: "Weigh the votes",
  report: "Write the verdict",
}

/** `narrow`: for a side column; caps the grid at 5 cards a row instead of 9. */
export function PipelineView({ stages, live, narrow = false }: { stages: Record<string, Stage>; live: boolean; narrow?: boolean }) {
  return (
    <div className="hud p-4 sm:p-5">
      <div className="mb-4 flex items-center gap-3">
        <h2 className="label-mono text-ink/80">Agent pipeline</h2>
        {live ? (
          <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-lime">
            <span className="size-1.5 rounded-full bg-lime [animation:aegis-pulse_1.4s_infinite]" aria-hidden="true" />
            live
          </span>
        ) : null}
        <span className="h-px flex-1 bg-hair" />
      </div>
      <ol className={cn("grid grid-cols-3 gap-2 sm:grid-cols-5", !narrow && "lg:grid-cols-9")}>
        {STAGES.map((name, i) => {
          const s = stages[name]
          const status = s?.status ?? "pending"
          const Icon = ICONS[name]
          return (
            <li
              key={name}
              aria-label={`${name}: ${status}`}
              title={s?.error || s?.summary || ROLE[name]}
              className={cn(
                "relative flex min-w-0 flex-col gap-1.5 rounded-xl border p-2.5 transition-colors duration-300",
                status === "pending" && "border-hair bg-white/[0.015] text-faint",
                status === "running" && "border-lime/60 bg-lime/[0.07] text-ink shadow-[0_0_18px_rgba(217,255,61,0.18)]",
                status === "done" && "border-lime/25 bg-lime/[0.035] text-ink",
                status === "failed" && "border-scam/50 bg-scam/[0.07] text-ink",
                status === "skipped" && "border-dashed border-hair bg-transparent text-faint",
              )}
            >
              <div className="flex items-center justify-between gap-1">
                <Icon className={cn("size-4", status === "running" || status === "done" ? "text-lime" : status === "failed" ? "text-scam" : "text-faint")} aria-hidden="true" />
                <StatusDot status={status} />
              </div>
              <span className="truncate font-mono text-[11px] font-semibold uppercase tracking-[0.1em]">
                <span className="text-faint">{i + 1}.</span> {name}
              </span>
              <span className="truncate text-[11px] text-muted-foreground">
                {status === "done" && s?.duration_s != null
                  ? seconds(s.duration_s)
                  : status === "running"
                    ? "working"
                    : status === "failed"
                      ? "degraded"
                      : status === "skipped"
                        ? "not needed"
                        : ROLE[name]}
              </span>
              {s?.summary && (status === "done" || status === "skipped") ? (
                <span className="line-clamp-2 text-[10.5px] leading-snug text-faint">{s.summary}</span>
              ) : null}
              {status === "failed" && s?.error ? <span className="line-clamp-2 text-[10.5px] leading-snug text-scam/80">{s.error}</span> : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  if (status === "running") return <Loader2 className="size-3.5 animate-spin text-lime" aria-hidden="true" />
  if (status === "done") return <Check className="size-3.5 text-lime" aria-hidden="true" />
  if (status === "failed") return <X className="size-3.5 text-scam" aria-hidden="true" />
  if (status === "skipped") return <Minus className="size-3.5 text-faint" aria-hidden="true" />
  return <span className="size-1.5 rounded-full bg-faint/60" aria-hidden="true" />
}
