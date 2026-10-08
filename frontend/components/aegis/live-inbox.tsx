"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowUpRight, Check, CheckCircle2, Copy, Loader2, Lock, Mail, MailOpen, Radio, Send, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { ErrorState, LoadingState, VerdictBadge } from "@/components/aegis/bits"
import { PipelineView } from "@/components/aegis/pipeline-view"
import { VerdictReport } from "@/components/aegis/verdict-report"
import { BorderBeam } from "@/components/ui/border-beam"
import { api, STAGES, type LiveInbox, type LiveInboxDetail, type LiveInboxItem, type Stage } from "@/lib/api"
import { seconds, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const POLL_MS = 2000
const MAIL_SUBJECT = "Test AEGIS"
const MAIL_BODY = "Paste or forward a suspicious email here, then send. AEGIS replies with its verdict."

export function LiveInboxView() {
  const [data, setData] = React.useState<LiveInbox | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [checkedAt, setCheckedAt] = React.useState<number | null>(null)
  const [fresh, setFresh] = React.useState<Set<string>>(new Set())
  const known = React.useRef<Set<string> | null>(null)
  const [pinned, setPinned] = React.useState<string | null>(null)

  React.useEffect(() => {
    let alive = true
    let timer = 0
    const tick = async () => {
      if (!document.hidden) {
        try {
          const d = await api.inboxLive()
          if (!alive) return
          // Rows that were not there on the previous poll are new mail: flash them.
          const keys = new Set(d.items.map((i) => i.key))
          if (known.current) {
            const added = d.items.filter((i) => !known.current!.has(i.key)).map((i) => i.key)
            if (added.length) {
              toast.success(added.length === 1 ? "New email received" : `${added.length} new emails received`, { description: "AEGIS is analyzing it now." })
              setFresh(new Set(added))
              window.setTimeout(() => alive && setFresh(new Set()), 4000)
            }
          }
          known.current = keys
          setData(d)
          setError(null)
          setCheckedAt(Date.now())
        } catch (e) {
          if (alive) setError(e instanceof Error ? e.message : "Could not reach the inbox.")
        }
      }
      if (alive) timer = window.setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [])

  if (!data && error) return <ErrorState message={error} />
  if (!data) return <LoadingState label="Connecting to the inbox" />
  if (!data.enabled || !data.address) {
    return <ErrorState message="The test inbox is not connected on this server. Set the AGENTBOXD_* variables in backend/.env and restart the backend." />
  }

  // The panel follows the newest email it may open, unless the visitor picked one.
  const openable = data.items
  const current = (pinned && openable.find((i) => i.key === pinned)) || openable[0] || null
  const following = !pinned || current?.key !== pinned

  return (
    <div className="flex flex-col gap-6">
      <AddressCard address={data.address} checkedAt={checkedAt} offline={!!error} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <section aria-labelledby="feed-title" className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="feed-title" className="label-mono text-ink/80">
              Inbox <span className="text-faint">{data.items.length}</span>
            </h2>
            <p className="text-xs text-faint">Newest first. Updates live.</p>
          </div>
          {data.items.length === 0 ? (
            <Waiting />
          ) : (
            <ul className="flex flex-col gap-2.5" aria-live="polite">
              {data.items.map((item) => (
                <InboxRow
                  key={item.key}
                  item={item}
                  fresh={fresh.has(item.key)}
                  selected={current?.key === item.key}
                  onSelect={() => setPinned(item.key === openable[0]?.key ? null : item.key)}
                />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="dissect-title" className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="dissect-title" className="label-mono text-ink/80">
              Live dissection
            </h2>
            {following ? (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-lime">
                <span className="size-1.5 rounded-full bg-lime [animation:aegis-pulse_2s_infinite]" aria-hidden="true" /> following newest
              </span>
            ) : (
              <button type="button" onClick={() => setPinned(null)} className="font-mono text-[11px] text-muted-foreground hover:text-lime">
                Follow newest
              </button>
            )}
          </div>
          {current ? (
            <Dissection key={current.key} item={current} />
          ) : (
            <div className="hud flex flex-col items-center gap-3 px-6 py-16 text-center">
              <Sparkles className="size-5 text-lime" aria-hidden="true" />
              <p className="label-mono text-[12px] text-muted-foreground">Nothing to dissect yet</p>
              <p className="max-w-sm text-sm text-faint">
                The moment an email lands, every agent&apos;s work on it streams in here, card by card, ending in the verdict.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

const DETAIL_POLL_MS = 1500

function stagesRecord(list: Stage[] | undefined): Record<string, Stage> {
  const out: Record<string, Stage> = {}
  for (const st of list ?? []) out[st.name] = st
  return out
}

/** One email taken apart live, partially censored by the server: the nine agents as they
 *  run (polled), the email itself, then the verdict report. */
function Dissection({ item }: { item: LiveInboxItem }) {
  const [detail, setDetail] = React.useState<LiveInboxDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let alive = true
    let timer = 0
    const tick = async () => {
      try {
        const d = await api.inboxLiveDetail(item.key)
        if (!alive) return
        setDetail(d)
        setError(null)
        if (d.status === "done" || d.status === "failed") return
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Could not open this email.")
      }
      if (alive) timer = window.setTimeout(tick, DETAIL_POLL_MS)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [item.key])

  const live = !detail || detail.status === "queued" || detail.status === "running"
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="hud flex min-w-0 flex-wrap items-center gap-3 px-5 py-4">
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-lg font-bold text-ink">{item.subject || "(no subject)"}</p>
          <p className="truncate font-mono text-[11px] text-faint">{[item.sender, timeAgo(item.created_at)].filter(Boolean).join(" · ")}</p>
        </div>
        {item.id ? (
          <Link href={`/cases/${encodeURIComponent(item.id)}`} className="inline-flex shrink-0 items-center gap-1 font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground hover:text-lime">
            Full case <ArrowUpRight className="size-3.5" aria-hidden="true" />
          </Link>
        ) : null}
      </div>
      {!detail && !error ? <LoadingState label="Opening the email" /> : null}
      {!detail && error ? <ErrorState message={error} /> : null}
      {detail ? <PipelineView stages={stagesRecord(detail.stages)} live={live} narrow /> : null}
      {detail && live ? (
        <p className="flex items-center justify-center gap-2 py-2 font-mono text-[12px] text-lime">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> Agents working. The verdict appears here when they finish.
        </p>
      ) : null}
      {detail ? <CensoredEmail detail={detail} /> : null}
      {detail?.status === "failed" ? <ErrorState message={detail.error || "The analysis failed. The pipeline fails closed, so treat this email as suspicious."} /> : null}
      {detail?.status === "done" ? <VerdictReport analysis={detail} mode="share" /> : null}
    </div>
  )
}

function CensoredEmail({ detail }: { detail: LiveInboxDetail }) {
  const e = detail.email
  if (!e) return null
  const rows = (
    [
      ["From", e.from],
      ["Subject", e.subject],
    ] as [string, string | null | undefined][]
  ).filter((r): r is [string, string] => !!r[1])
  return (
    <section className="hud flex min-w-0 flex-col gap-3 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="label-mono text-ink/80">The email</h3>
        <span className="inline-flex items-center gap-1.5 font-mono text-[10.5px] text-faint">
          <Lock className="size-3" aria-hidden="true" /> names, addresses and numbers partially censored
        </span>
      </div>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
        {rows.map(([k, v]) => (
          <React.Fragment key={k}>
            <dt className="label-mono pt-0.5 text-[9.5px]">{k}</dt>
            <dd className="break-words font-mono text-[12.5px] text-ink/90">{v}</dd>
          </React.Fragment>
        ))}
      </dl>
      {e.text ? (
        <pre className="thin-scroll max-h-56 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-hair bg-black/30 p-3 font-mono text-[12px] leading-relaxed text-ink/80">
          {e.text}
        </pre>
      ) : null}
    </section>
  )
}

function AddressCard({ address, checkedAt, offline }: { address: string; checkedAt: number | null; offline: boolean }) {
  const [copied, setCopied] = React.useState(false)
  const mailto = `mailto:${address}?subject=${encodeURIComponent(MAIL_SUBJECT)}&body=${encodeURIComponent(MAIL_BODY)}`
  const steps = [
    { icon: Send, title: "Send any email", text: "A scam you received, a forward, or one you write yourself." },
    { icon: Radio, title: "AEGIS picks it up", text: "Usually within a few seconds of arriving." },
    { icon: Sparkles, title: "Watch it here", text: "Nine agents run live below, then the verdict is replied to you." },
  ]
  return (
    <BorderBeam className="min-w-0 rounded-[1.5rem]" radius={24} duration={9}>
      <section aria-labelledby="addr-title" className="hud flex flex-col gap-6 p-5 sm:p-7 [--hud-r:1.5rem]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p id="addr-title" className="label-mono text-lime">
            Test inbox address
          </p>
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10.5px] uppercase tracking-[0.14em]",
              offline ? "border-scam/40 text-scam" : "border-lime/30 text-lime",
            )}
          >
            <span
              className={cn("size-1.5 rounded-full", offline ? "bg-scam" : "bg-lime shadow-[0_0_10px_var(--aegis-lime)] [animation:aegis-pulse_2s_infinite]")}
              aria-hidden="true"
            />
            {offline ? "Reconnecting" : "Listening"}
            {checkedAt && !offline ? <span className="normal-case tracking-normal text-faint">· live</span> : null}
          </span>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <code className="min-w-0 flex-1 break-words rounded-xl border border-hair bg-black/40 px-4 py-3.5 font-mono text-lg font-semibold text-ink sm:text-2xl">
            {address.split("@")[0]}
            <wbr />@{address.split("@").slice(1).join("@")}
          </code>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() =>
                navigator.clipboard.writeText(address).then(
                  () => {
                    setCopied(true)
                    toast.success("Address copied")
                    window.setTimeout(() => setCopied(false), 1600)
                  },
                  () => toast.error("Could not copy"),
                )
              }
              className="inline-flex h-12 items-center gap-2 rounded-full bg-lime px-5 text-sm font-semibold text-black shadow-[0_0_24px_rgba(217,255,61,0.3)] transition-transform active:scale-[0.98]"
            >
              {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <a
              href={mailto}
              className="inline-flex h-12 items-center gap-2 rounded-full border border-hair bg-surface/80 px-5 text-sm font-medium text-ink transition-colors hover:border-lime/40"
            >
              <Mail className="size-4 text-lime" aria-hidden="true" />
              Open mail app
            </a>
          </div>
        </div>

        <ol className="grid gap-3 sm:grid-cols-3">
          {steps.map((s, i) => (
            <li key={s.title} className="flex gap-3 rounded-xl border border-hair bg-black/20 p-3.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-lime/30 bg-lime/5 font-mono text-[11px] text-lime">{i + 1}</span>
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                  <s.icon className="size-3.5 text-lime" aria-hidden="true" /> {s.title}
                </span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{s.text}</span>
              </span>
            </li>
          ))}
        </ol>

        <p className="flex items-start gap-2 text-xs text-faint">
          <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          This is a public test inbox: every email sent here is shown on this page with names, addresses and numbers partially censored, and its
          verdict is replied to the sender. Do not send personal mail.
        </p>
      </section>
    </BorderBeam>
  )
}

function Waiting() {
  return (
    <div className="hud flex flex-col items-center gap-4 px-6 py-14 text-center">
      <span className="relative flex size-14 items-center justify-center">
        <span className="absolute inset-0 rounded-full border border-lime/30 [animation:aegis-pulse_2.4s_ease-in-out_infinite]" aria-hidden="true" />
        <span className="absolute inset-2 rounded-full border border-lime/20" aria-hidden="true" />
        <MailOpen className="size-5 text-lime" aria-hidden="true" />
      </span>
      <p className="label-mono text-[12px] text-muted-foreground">Waiting for mail</p>
      <p className="max-w-sm text-sm text-faint">Send an email to the address above. It appears here the moment it lands, and you can watch every agent work on it.</p>
    </div>
  )
}

function InboxRow({ item, fresh, selected, onSelect }: { item: LiveInboxItem; fresh: boolean; selected: boolean; onSelect?: () => void }) {
  const byName = new Map(item.stages.map((s) => [s.name, s.status]))
  const running = item.stages.find((s) => s.status === "running")?.name
  const doneCount = item.stages.filter((s) => s.status === "done" || s.status === "skipped").length
  const working = item.status === "queued" || item.status === "running"
  const statusText =
    item.status === "queued"
      ? "Queued"
      : item.status === "failed"
        ? "Analysis failed"
        : working
          ? `Running ${running ?? "pipeline"}`
          : `Analyzed${item.duration_s ? ` in ${seconds(item.duration_s)}` : ""}`

  const body = (
    <>
      <span className="flex min-w-0 items-start justify-between gap-3">
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[14px] font-medium text-ink">{item.subject || "(no subject)"}</span>
          <span className="truncate font-mono text-[11px] text-faint">{[item.sender, timeAgo(item.created_at)].filter(Boolean).join(" · ")}</span>
          {item.preview ? <span className="mt-1 line-clamp-2 text-[12px] leading-snug text-muted-foreground">{item.preview}</span> : null}
        </span>
        <span className="shrink-0">
          {working ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-lime/30 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-lime">
              <Loader2 className="size-3 animate-spin" aria-hidden="true" /> live
            </span>
          ) : (
            <VerdictBadge label={item.label} />
          )}
        </span>
      </span>
      <ol className="flex gap-1" aria-label={`${doneCount} of ${STAGES.length} stages finished`}>
        {STAGES.map((name) => {
          const st = byName.get(name) ?? "pending"
          return (
            <li
              key={name}
              title={`${name}: ${st}`}
              className={cn(
                "h-1.5 flex-1 rounded-full",
                st === "done" && "bg-lime",
                st === "running" && "bg-lime/70 [animation:aegis-pulse_1.2s_infinite]",
                st === "skipped" && "bg-white/20",
                st === "failed" && "bg-scam",
                st === "pending" && "bg-white/[0.07]",
              )}
            />
          )
        })}
      </ol>
      <span className="flex items-center justify-between gap-2 font-mono text-[11px] text-muted-foreground">
        <span className="truncate">{statusText}</span>
        {item.replied ? (
          <span className="inline-flex shrink-0 items-center gap-1 text-safe">
            <CheckCircle2 className="size-3" aria-hidden="true" /> replied
          </span>
        ) : null}
      </span>
    </>
  )

  const cls = cn(
    "hud flex w-full min-w-0 flex-col gap-2.5 p-4 text-left transition-[box-shadow,border-color] duration-700",
    fresh && "border-lime/60 shadow-[0_0_28px_-6px_rgba(217,255,61,0.45)]",
    selected && "border-lime/50 bg-lime/[0.04]",
    onSelect && "hud-interactive",
  )
  return (
    <li>
      {onSelect ? (
        <button type="button" onClick={onSelect} aria-pressed={selected} className={cls}>
          {body}
        </button>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  )
}
