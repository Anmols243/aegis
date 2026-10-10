"use client"

import * as React from "react"
import Link from "next/link"
import { Check, Copy, Mail } from "lucide-react"
import { toast } from "sonner"

import { api, type PublicConfig, type Stats } from "@/lib/api"
import { seconds } from "@/lib/format"

function useCountUp(target: number, ms = 900): number {
  const [v, setV] = React.useState(0)
  React.useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const id = requestAnimationFrame(() => setV(target))
      return () => cancelAnimationFrame(id)
    }
    let raf = 0
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      setV(Math.round(target * (1 - Math.pow(1 - t, 3))))
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}

function Counter({ value, label, tone }: { value: number; label: string; tone?: string }) {
  const v = useCountUp(value)
  return (
    <div className="flex flex-col gap-1 px-5 py-5">
      <span className={`font-mono text-3xl font-medium tabular-nums ${tone ?? "text-ink"}`}>{String(v).padStart(2, "0")}</span>
      <span className="label-mono">{label}</span>
    </div>
  )
}

export function LiveCounters() {
  const [stats, setStats] = React.useState<Stats | null>(null)
  const [failed, setFailed] = React.useState(false)

  React.useEffect(() => {
    let alive = true
    const load = () =>
      api
        .stats()
        .then((s) => {
          if (alive) {
            setStats(s)
            setFailed(false)
          }
        })
        .catch(() => alive && setFailed(true))
    load()
    const id = window.setInterval(load, 15000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  if (failed && !stats) {
    return <p className="label-mono text-faint">Live counters unavailable: the analysis service is offline.</p>
  }
  return (
    <div className="hud grid grid-cols-2 divide-hair overflow-hidden md:grid-cols-4 [&>*]:border-hair [&>*:nth-child(n+3)]:border-t md:[&>*:nth-child(n+3)]:border-t-0 [&>*:nth-child(even)]:border-l md:[&>*:not(:first-child)]:border-l">
      <Counter value={stats?.total ?? 0} label="emails analyzed" />
      <Counter value={stats?.by_label?.SCAM ?? 0} label="scams caught" tone="text-scam" />
      <Counter value={stats?.campaigns ?? 0} label="campaigns linked" tone="text-lime" />
      <div className="flex flex-col gap-1 px-5 py-5">
        <span className="font-mono text-3xl font-medium tabular-nums text-ink">{stats ? seconds(stats.avg_duration_s) : "--"}</span>
        <span className="label-mono">avg analysis time</span>
      </div>
    </div>
  )
}

/** Opens the live test inbox page. Shown only while the AgentBoxD inbox is live. */
export function EmailTestButton() {
  const [cfg, setCfg] = React.useState<PublicConfig | null>(null)
  React.useEffect(() => {
    api.publicConfig().then(setCfg).catch(() => setCfg(null))
  }, [])
  const addr = cfg?.inbox_address
  if (!addr || !cfg?.features?.inbox) return null
  return (
    <Link
      href="/live"
      title="Test the system with a real email"
      className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-lime/40 bg-surface/80 px-7 py-2 text-sm font-medium text-ink backdrop-blur transition-colors hover:border-lime hover:text-lime"
    >
      <Mail className="size-4 shrink-0 text-lime" aria-hidden="true" />
      Test system
    </Link>
  )
}

export function InboxCallout() {
  const [cfg, setCfg] = React.useState<PublicConfig | null>(null)
  const [copied, setCopied] = React.useState(false)
  React.useEffect(() => {
    api.publicConfig().then(setCfg).catch(() => setCfg(null))
  }, [])
  const addr = cfg?.inbox_address
  if (!addr) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 text-sm text-muted-foreground">
      <Mail className="size-4 text-lime" aria-hidden="true" />
      <span>or forward suspicious mail to</span>
      <code className="rounded-md border border-hair bg-surface px-2 py-0.5 font-mono text-[13px] text-ink">{addr}</code>
      <button
        type="button"
        aria-label="Copy inbox address"
        onClick={() => {
          navigator.clipboard.writeText(addr).then(
            () => {
              setCopied(true)
              toast.success("Inbox address copied")
              window.setTimeout(() => setCopied(false), 1600)
            },
            () => toast.error("Could not copy"),
          )
        }}
        className="inline-flex size-7 items-center justify-center rounded-md border border-hair text-muted-foreground transition-colors hover:border-lime/50 hover:text-lime"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
      <span>and get the verdict by email</span>
    </div>
  )
}
