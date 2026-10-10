"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowUpRight, AtSign, FileText, Globe, Link2, type LucideIcon, Network, Phone } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/aegis/bits"
import { api, type Campaign, type CampaignsResponse, type Label } from "@/lib/api"
import { LABEL_META, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

type Kind = "sender" | "domain" | "url" | "phone" | "template"

const KINDS: { kind: Kind; name: string; plural: string; icon: LucideIcon; color: string }[] = [
  { kind: "sender", name: "sender", plural: "Sender addresses", icon: AtSign, color: "#9ec5ff" },
  { kind: "domain", name: "domain", plural: "Domains", icon: Globe, color: "#d9ff3d" },
  { kind: "url", name: "link", plural: "Links", icon: Link2, color: "#c6a8ff" },
  { kind: "phone", name: "phone", plural: "Phone numbers", icon: Phone, color: "#7ee8fa" },
  { kind: "template", name: "template", plural: "Message template", icon: FileText, color: "#8a8f98" },
]

// SVG strokes take the verdict colors as hex (same values as globals.css).
const VERDICT_HEX: Record<string, string> = { SCAM: "#ff5c5c", SUSPICIOUS: "#ffb224", LIKELY_SAFE: "#3ddc97" }

// Shared webmail providers say nothing about the operator, so the full address names the campaign instead.
const WEBMAIL = new Set(["gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com", "proton.me", "aol.com"])

/** The most specific operator identifier: sender domain, else domain, link host, phone. */
function operatorOf(c: Campaign): string {
  const sender = c.infra.find((i) => i.kind === "sender")?.value
  const senderDomain = sender?.split("@")[1]
  if (senderDomain && !WEBMAIL.has(senderDomain)) return senderDomain
  if (sender) return sender
  const first = c.infra.find((i) => i.kind === "domain") ?? c.infra.find((i) => i.kind === "url") ?? c.infra.find((i) => i.kind === "phone")
  return first ? first.value.split("/")[0] : "Shared message template"
}

/** Line-break opportunities after dots, hyphens and @, so a domain wraps at its parts. */
function softBreaks(s: string): React.ReactNode {
  return s.split(/(?<=[.@-])/).map((part, i) => (
    <React.Fragment key={i}>
      {i > 0 ? <wbr /> : null}
      {part}
    </React.Fragment>
  ))
}

function linkedBy(c: Campaign): string {
  const kinds = KINDS.filter((k) => c.infra.some((i) => i.kind === k.kind)).map((k) => k.name)
  if (kinds.length <= 1) return kinds[0] ?? "infrastructure"
  return `${kinds.slice(0, -1).join(", ")} and ${kinds[kinds.length - 1]}`
}

function verdictCounts(c: Campaign): Record<Label, number> {
  const out: Record<Label, number> = { SCAM: 0, SUSPICIOUS: 0, LIKELY_SAFE: 0 }
  for (const a of c.analyses) if (a.label) out[a.label] += 1
  return out
}

function seenRange(c: Campaign): { first: string | null; last: string | null } {
  const ts = c.analyses.map((a) => a.created_at).filter((t): t is string => !!t).sort()
  return { first: ts[0] ?? null, last: ts[ts.length - 1] ?? null }
}

type EmailGroup = { key: string; subject: string; label: Label | null; ids: string[]; latestId: string; latestAt: string }

/** Identical subjects collapse into one row; the link opens the newest case. */
function groupEmails(c: Campaign): EmailGroup[] {
  const groups = new Map<string, EmailGroup>()
  for (const a of c.analyses) {
    const key = a.subject || a.id
    const at = a.created_at ?? ""
    const g = groups.get(key)
    if (!g) groups.set(key, { key, subject: a.subject || a.id, label: a.label, ids: [a.id], latestId: a.id, latestAt: at })
    else {
      g.ids.push(a.id)
      if (a.label === "SCAM") g.label = "SCAM"
      if (at > g.latestAt) {
        g.latestAt = at
        g.latestId = a.id
      }
    }
  }
  return [...groups.values()].sort((x, y) => y.ids.length - x.ids.length || y.latestAt.localeCompare(x.latestAt))
}

export function CampaignsView() {
  const [data, setData] = React.useState<CampaignsResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)

  React.useEffect(() => {
    let alive = true
    api
      .campaigns()
      .then((d) => {
        if (alive) {
          setData(d)
          setError(null)
        }
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : "Could not load campaigns."))
    return () => {
      alive = false
    }
  }, [attempt])

  if (error && !data) return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />
  if (!data) return <LoadingState label="Loading campaigns" />

  if (data.campaigns.length === 0) {
    return (
      <div className="hud">
        <EmptyState title="No campaigns yet">A campaign appears when two or more flagged emails share a sender, domain, link, phone number or message template.</EmptyState>
      </div>
    )
  }

  const selected = data.campaigns.find((c) => c.id === selectedId) ?? data.campaigns[0]

  return (
    <div className="flex flex-col gap-6">
      <StatStrip campaigns={data.campaigns} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <CampaignList campaigns={data.campaigns} selectedId={selected.id} onSelect={setSelectedId} />
        <CampaignDetail key={selected.id} campaign={selected} data={data} />
      </div>
    </div>
  )
}

function StatStrip({ campaigns }: { campaigns: Campaign[] }) {
  const reports = campaigns.reduce((n, c) => n + c.analyses.length + (c.hidden_count ?? 0), 0)
  const indicators = new Set(campaigns.flatMap((c) => c.infra.map((i) => `${i.kind}:${i.value}`)))
  const domains = new Set(campaigns.flatMap((c) => c.infra.filter((i) => i.kind === "domain").map((i) => i.value)))
  const stats = [
    { label: "Active campaigns", value: campaigns.length },
    { label: "Linked reports", value: reports },
    { label: "Operator domains", value: domains.size },
    { label: "Shared indicators", value: indicators.size },
  ]
  return (
    <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {stats.map((s) => (
        <div key={s.label} className="hud px-5 py-4">
          <dt className="label-mono">{s.label}</dt>
          <dd className="mt-1.5 font-display text-3xl font-bold tabular-nums text-ink">{s.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function CampaignList({ campaigns, selectedId, onSelect }: { campaigns: Campaign[]; selectedId: string; onSelect: (id: string) => void }) {
  return (
    <aside aria-labelledby="camp-list" className="hud flex min-w-0 flex-col p-2">
      <h2 id="camp-list" className="label-mono flex items-center justify-between px-3 pb-2 pt-3">
        <span>Campaigns</span>
        <span className="text-faint">{campaigns.length}</span>
      </h2>
      <ul className="flex flex-col gap-1">
        {campaigns.map((c, i) => {
          const active = c.id === selectedId
          const v = verdictCounts(c)
          const total = c.analyses.length
          const reports = total + (c.hidden_count ?? 0)
          return (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "group flex w-full min-w-0 flex-col gap-2 rounded-xl border px-3 py-3 text-left transition-colors",
                  active ? "border-lime/40 bg-lime/[0.06]" : "border-transparent hover:border-hair hover:bg-white/[0.03]",
                )}
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className={cn("font-mono text-[11px] tabular-nums", active ? "text-lime" : "text-faint")}>{String(i + 1).padStart(2, "0")}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-[13px] font-semibold text-ink">{operatorOf(c)}</span>
                  <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                    {reports} {reports === 1 ? "report" : "reports"}
                  </span>
                </span>
                <span className="flex items-center gap-3 pl-[30px]">
                  <span className="flex h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]" aria-label={`${v.SCAM} scam, ${v.SUSPICIOUS} suspicious`}>
                    <span style={{ width: `${(v.SCAM / Math.max(total, 1)) * 100}%`, background: LABEL_META.SCAM.color }} />
                    <span style={{ width: `${(v.SUSPICIOUS / Math.max(total, 1)) * 100}%`, background: LABEL_META.SUSPICIOUS.color }} />
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 text-faint" aria-label={`Linked by ${linkedBy(c)}`}>
                    {KINDS.filter((k) => c.infra.some((x) => x.kind === k.kind)).map((k) => (
                      <k.icon key={k.kind} className="size-3" aria-hidden="true" />
                    ))}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

function CampaignDetail({ campaign: c, data }: { campaign: Campaign; data: CampaignsResponse }) {
  const v = verdictCounts(c)
  const { first, last } = seenRange(c)
  const meta = [
    { label: "Reports", value: `${c.analyses.length}${c.hidden_count ? ` + ${c.hidden_count} private` : ""}` },
    { label: "First seen", value: timeAgo(first) || "unknown" },
    { label: "Last seen", value: timeAgo(last) || "unknown" },
    { label: "Verdicts", value: [v.SCAM && `${v.SCAM} scam`, v.SUSPICIOUS && `${v.SUSPICIOUS} suspicious`].filter(Boolean).join(", ") || "none" },
  ]

  return (
    <section aria-labelledby="camp-title" className="hud flex min-w-0 flex-col gap-6 p-5 sm:p-6">
      <header className="flex flex-col gap-4">
        <div className="min-w-0">
          <p className="label-mono mb-2 flex items-center gap-2">
            <Network className="size-3.5 text-lime" aria-hidden="true" /> Campaign <span className="normal-case tracking-normal text-faint">{c.id}</span>
          </p>
          <h2 id="camp-title" className="break-all font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">
            {operatorOf(c)}
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {c.analyses.length + (c.hidden_count ?? 0)} flagged emails reuse the same {linkedBy(c)}: one operator behind every message below.
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-hair bg-hair sm:grid-cols-4">
          {meta.map((m) => (
            <div key={m.label} className="bg-surface px-4 py-3">
              <dt className="label-mono text-[9.5px]">{m.label}</dt>
              <dd className="truncate pt-1 font-mono text-[12.5px] text-ink">{m.value}</dd>
            </div>
          ))}
        </dl>
      </header>

      <OperatorMap campaign={c} data={data} />
    </section>
  )
}

type Path = { id: string; d: string; color: string; weight: number }
type Focus = { type: "email"; key: string } | { type: "infra"; id: string } | null

/**
 * Emails on the left, the operator in the middle, the infrastructure they share on the right.
 * Deterministic layout (no physics), so every label stays readable. Hover or focus a row to trace it.
 */
function OperatorMap({ campaign: c, data }: { campaign: Campaign; data: CampaignsResponse }) {
  const emails = React.useMemo(() => groupEmails(c), [c])

  // Which shared indicators each email carries, from the graph links.
  const carries = React.useMemo(() => {
    const byAnalysis = new Map<string, Set<string>>()
    for (const l of data.graph.links) {
      if (!l.source.startsWith("a:")) continue
      const aid = l.source.slice(2)
      if (!byAnalysis.has(aid)) byAnalysis.set(aid, new Set())
      byAnalysis.get(aid)!.add(l.target)
    }
    return byAnalysis
  }, [data])

  const infra = React.useMemo(
    () =>
      KINDS.map((k) => ({
        ...k,
        items: c.infra
          .filter((i) => i.kind === k.kind)
          .map((i) => {
            const id = `${i.kind}:${i.value}`
            const coverage = c.analyses.filter((a) => carries.get(a.id)?.has(id)).length
            return { id, value: i.value, coverage }
          })
          .sort((a, b) => b.coverage - a.coverage),
      })).filter((k) => k.items.length > 0),
    [c, carries],
  )

  const emailCarries = React.useCallback(
    (g: EmailGroup) => {
      const out = new Set<string>()
      for (const id of g.ids) for (const x of carries.get(id) ?? []) out.add(x)
      return out
    },
    [carries],
  )

  const [focus, setFocus] = React.useState<Focus>(null)
  const litInfra: Set<string> | null =
    focus?.type === "email" ? emailCarries(emails.find((e) => e.key === focus.key)!) : focus?.type === "infra" ? new Set([focus.id]) : null
  const litEmails: Set<string> | null =
    focus?.type === "infra" ? new Set(emails.filter((e) => emailCarries(e).has(focus.id)).map((e) => e.key)) : focus?.type === "email" ? new Set([focus.key]) : null

  // Connector curves, measured from the rendered rows.
  const wrapRef = React.useRef<HTMLDivElement>(null)
  const hubRef = React.useRef<HTMLDivElement>(null)
  const rowRefs = React.useRef(new Map<string, HTMLElement>())
  const [paths, setPaths] = React.useState<{ left: Path[]; right: Path[]; w: number; h: number }>({ left: [], right: [], w: 0, h: 0 })

  React.useLayoutEffect(() => {
    const wrap = wrapRef.current
    const hub = hubRef.current
    if (!wrap || !hub) return
    const measure = () => {
      const W = wrap.getBoundingClientRect()
      const H = hub.getBoundingClientRect()
      if (getComputedStyle(hub).display === "none" || H.width === 0) return
      const hubY = H.top + H.height / 2 - W.top
      const curve = (x1: number, y1: number, x2: number, y2: number) => {
        const dx = (x2 - x1) / 2
        return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`
      }
      const left: Path[] = emails.flatMap((e) => {
        const el = rowRefs.current.get(`e:${e.key}`)
        if (!el) return []
        const r = el.getBoundingClientRect()
        return [{ id: e.key, d: curve(r.right - W.left, r.top + r.height / 2 - W.top, H.left - W.left, hubY), color: VERDICT_HEX[e.label ?? ""] ?? "#8a8f98", weight: e.ids.length }]
      })
      const right: Path[] = infra.flatMap((k) =>
        k.items.flatMap((it) => {
          const el = rowRefs.current.get(`i:${it.id}`)
          if (!el) return []
          const r = el.getBoundingClientRect()
          return [{ id: it.id, d: curve(H.right - W.left, hubY, r.left - W.left, r.top + r.height / 2 - W.top), color: k.color, weight: it.coverage }]
        }),
      )
      setPaths({ left, right, w: W.width, h: W.height })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [emails, infra])

  const setRow = (key: string) => (el: HTMLElement | null) => {
    if (el) rowRefs.current.set(key, el)
    else rowRefs.current.delete(key)
  }

  const total = c.analyses.length
  const strokeFor = (lit: boolean | null) => (lit === null ? 0.32 : lit ? 0.95 : 0.06)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="label-mono text-ink/80">Operator map</h3>
        <p className="text-xs text-faint">Hover a row to trace it. Emails open their case.</p>
      </div>

      <div ref={wrapRef} className="relative overflow-hidden rounded-xl border border-hair bg-black/30 p-4 sm:p-5" onMouseLeave={() => setFocus(null)}>
        <svg className="pointer-events-none absolute inset-0 hidden md:block" width={paths.w} height={paths.h} aria-hidden="true">
          {paths.left.map((p) => {
            const lit = litEmails ? litEmails.has(p.id) : null
            return (
              <g key={`l:${p.id}`}>
                <path d={p.d} fill="none" stroke={p.color} strokeOpacity={strokeFor(lit)} strokeWidth={1 + Math.min(p.weight, 4) * 0.5} className="transition-[stroke-opacity] duration-200" />
                {lit ? <path d={p.d} fill="none" stroke={p.color} strokeWidth={2} strokeDasharray="3 9" className="aegis-flow" /> : null}
              </g>
            )
          })}
          {paths.right.map((p) => {
            const lit = litInfra ? litInfra.has(p.id) : null
            return (
              <g key={`r:${p.id}`}>
                <path d={p.d} fill="none" stroke={p.color} strokeOpacity={strokeFor(lit)} strokeWidth={1 + (p.weight / Math.max(total, 1)) * 2} className="transition-[stroke-opacity] duration-200" />
                {lit ? <path d={p.d} fill="none" stroke={p.color} strokeWidth={2} strokeDasharray="3 9" className="aegis-flow" /> : null}
              </g>
            )
          })}
        </svg>

        <div className="relative grid items-center gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,150px)_minmax(0,1.15fr)] md:gap-12">
          {/* emails */}
          <div className="flex min-w-0 flex-col gap-2">
            <p className="label-mono text-[9.5px]">
              Emails <span className="text-faint">{total}</span>
            </p>
            <ul className="flex flex-col gap-2">
              {emails.map((e) => {
                const dim = litEmails !== null && !litEmails.has(e.key)
                return (
                  <li key={e.key}>
                    <Link
                      ref={setRow(`e:${e.key}`)}
                      href={`/cases/${encodeURIComponent(e.latestId)}`}
                      onMouseEnter={() => setFocus({ type: "email", key: e.key })}
                      onFocus={() => setFocus({ type: "email", key: e.key })}
                      onBlur={() => setFocus(null)}
                      className={cn(
                        "group flex min-w-0 items-center gap-2.5 rounded-lg border border-hair bg-surface/90 px-3 py-2.5 transition-[opacity,border-color] duration-200 hover:border-white/20",
                        dim && "opacity-35",
                      )}
                    >
                      <span className="size-2 shrink-0 rounded-full" style={{ background: VERDICT_HEX[e.label ?? ""] ?? "#8a8f98", boxShadow: `0 0 8px ${VERDICT_HEX[e.label ?? ""] ?? "transparent"}` }} />
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="line-clamp-2 text-[13px] leading-snug text-ink group-hover:text-lime" title={e.subject}>
                          {e.subject}
                        </span>
                        <span className="font-mono text-[10.5px] text-faint">
                          {e.label ? LABEL_META[e.label].text.toLowerCase() : "pending"}
                          {e.latestAt ? ` · ${timeAgo(e.latestAt)}` : ""}
                        </span>
                      </span>
                      {e.ids.length > 1 ? (
                        <span className="shrink-0 rounded-full border border-hair px-1.5 py-0.5 font-mono text-[10.5px] text-muted-foreground" title={`${e.ids.length} copies of this email`}>
                          x{e.ids.length}
                        </span>
                      ) : null}
                      <ArrowUpRight className="size-3.5 shrink-0 text-faint group-hover:text-lime" aria-hidden="true" />
                    </Link>
                  </li>
                )
              })}
            </ul>
            {c.hidden_count ? (
              <p className="px-1 text-[11.5px] text-faint">
                + {c.hidden_count} private {c.hidden_count === 1 ? "report" : "reports"} from other people. Their content stays private.
              </p>
            ) : null}
          </div>

          {/* operator hub */}
          <div className="flex justify-center">
            <div
              ref={hubRef}
              className="relative flex w-full max-w-[220px] flex-col items-center gap-2 rounded-2xl border border-lime/40 bg-[#0d1009] px-3 py-4 text-center shadow-[0_0_32px_-8px_rgba(217,255,61,0.35)]"
            >
              <span className="relative flex size-10 items-center justify-center rounded-full border border-lime/50 bg-lime/10">
                <span className="absolute inset-0 rounded-full border border-lime/40 [animation:aegis-pulse_2.4s_ease-in-out_infinite]" aria-hidden="true" />
                <Network className="size-4.5 text-lime" aria-hidden="true" />
              </span>
              <span className="label-mono text-[9px] text-lime">Operator</span>
              <span className="break-words font-mono text-[12px] font-semibold leading-snug text-ink">{softBreaks(operatorOf(c))}</span>
              <span className="font-mono text-[10px] text-faint">
                {total} {total === 1 ? "email" : "emails"} · {c.infra.length} indicators
              </span>
            </div>
          </div>

          {/* infrastructure */}
          <div className="flex min-w-0 flex-col gap-3">
            <p className="label-mono text-[9.5px]">
              Shared infrastructure <span className="text-faint">{c.infra.length}</span>
            </p>
            {infra.map((k) => (
              <div key={k.kind} className="flex flex-col gap-1.5">
                <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em]" style={{ color: k.color }}>
                  <k.icon className="size-3" aria-hidden="true" /> {k.plural}
                </p>
                <ul className="flex flex-col gap-1.5">
                  {k.items.map((it) => {
                    const dim = litInfra !== null && !litInfra.has(it.id)
                    return (
                      <li
                        key={it.id}
                        ref={setRow(`i:${it.id}`)}
                        tabIndex={0}
                        onMouseEnter={() => setFocus({ type: "infra", id: it.id })}
                        onFocus={() => setFocus({ type: "infra", id: it.id })}
                        onBlur={() => setFocus(null)}
                        className={cn(
                          "flex min-w-0 items-center gap-2.5 rounded-lg border border-hair bg-surface/90 px-3 py-2 outline-none transition-[opacity,border-color] duration-200 hover:border-white/20 focus-visible:border-lime/60",
                          dim && "opacity-35",
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink/90" title={it.value}>
                          {k.kind === "template" ? `identical body #${it.value.slice(0, 8)}` : it.value}
                        </span>
                        <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-muted-foreground" title={`Found in ${it.coverage} of ${total} emails`}>
                          {it.coverage}/{total}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
