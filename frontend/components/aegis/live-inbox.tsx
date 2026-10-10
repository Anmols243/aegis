"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowUpRight, CheckCircle2, ChevronRight, Loader2, Lock, MailOpen, Send, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { ErrorState, LoadingState, SeverityPill, VerdictBadge } from "@/components/aegis/bits"
import { HERO_PRIMARY, HERO_SECONDARY, PageHero } from "@/components/aegis/page-hero"
import { api, ApiError, STAGES, type LiveInbox, type LiveInboxDetail, type LiveInboxItem, type Stage } from "@/lib/api"
import { LABEL_META, pct, seconds, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const POLL_MS = 2000
const DETAIL_POLL_MS = 1500
const MAIL_SUBJECT = "Test AEGIS"
const MAIL_BODY = "Paste a suspicious email below this line, then send.\n\n"
const STEPS = ["Open your mail app", "Paste a suspicious email", "Send it and watch below"]

/**
 * The live test inbox: one screen, no long scroll. A "Test the system" hero on top whose
 * buttons open a message with the address and this browser's code already filled in, then
 * the inbox feed and the dissection side by side; each scrolls inside its own panel.
 */
export function LiveInboxView() {
  const [data, setData] = React.useState<LiveInbox | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [fresh, setFresh] = React.useState<Set<string>>(new Set())
  // /live?email=<key> (linked from Cases) opens that email instead of following the newest.
  // Safe on the server: nothing that depends on it renders before the first poll returns.
  const [pinned, setPinned] = React.useState<string | null>(() =>
    typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("email"),
  )
  const known = React.useRef<Set<string> | null>(null)

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

  const address = data?.enabled ? data.address : null
  const state: HeroState = !data ? (error ? "offline" : "connecting") : !address ? "offline" : error ? "reconnecting" : "listening"
  const hero = <TestHero address={address} code={data?.code ?? null} state={state} />

  if (!data || !address) {
    return (
      <div className="flex flex-col gap-4">
        {hero}
        {!data && error ? (
          <ErrorState message={error} />
        ) : !data ? (
          <LoadingState label="Connecting to the inbox" />
        ) : (
          <ErrorState message="The test inbox is not connected on this server. Set the AGENTBOXD_* variables in backend/.env and restart the backend." />
        )}
      </div>
    )
  }

  // The panel follows the newest email unless the visitor picked one.
  const items = data.items
  const current = (pinned && items.find((i) => i.key === pinned)) || items[0] || null
  const following = !pinned || current?.key !== pinned

  return (
    <div className="flex flex-col gap-4">
      {hero}
      <div className="grid gap-4 lg:h-[calc(100dvh-19rem)] lg:min-h-[560px] lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
        <section aria-labelledby="feed-title" className="hud flex min-h-0 min-w-0 flex-col p-2">
          <div className="flex items-baseline justify-between gap-2 px-3 pb-2 pt-3">
            <h2 id="feed-title" className="label-mono text-ink/80">
              Inbox <span className="text-faint">{items.length}</span>
            </h2>
            <span className="font-mono text-[10.5px] text-faint">newest first</span>
          </div>
          {items.length === 0 ? (
            <Waiting />
          ) : (
            <ul className="thin-scroll flex max-h-[45vh] min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto px-1 pb-1 lg:max-h-none" aria-live="polite">
              {items.map((item) => (
                <InboxRow
                  key={item.key}
                  item={item}
                  fresh={fresh.has(item.key)}
                  selected={current?.key === item.key}
                  onSelect={() => setPinned(item.key === items[0]?.key ? null : item.key)}
                />
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Live dissection" className="hud flex min-h-[480px] min-w-0 flex-col overflow-hidden lg:min-h-0">
          {current ? (
            <Dissection key={current.key} item={current} following={following} onFollow={() => setPinned(null)} />
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-16 text-center">
              <Sparkles className="size-5 text-lime" aria-hidden="true" />
              <p className="label-mono text-[12px] text-muted-foreground">Live dissection</p>
              <p className="max-w-sm text-sm text-faint">The moment an email lands, every agent&apos;s work on it streams in here, ending in the verdict.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

type HeroState = "connecting" | "listening" | "reconnecting" | "offline"

const STATE_PILL: Record<HeroState, { text: string; tone: string; dot: string }> = {
  connecting: { text: "Connecting", tone: "border-hair text-muted-foreground", dot: "bg-muted-foreground [animation:aegis-pulse_1.2s_infinite]" },
  listening: { text: "Listening", tone: "border-lime/30 text-lime", dot: "bg-lime shadow-[0_0_10px_var(--aegis-lime)] [animation:aegis-pulse_2s_infinite]" },
  reconnecting: { text: "Reconnecting", tone: "border-scam/40 text-scam", dot: "bg-scam" },
  offline: { text: "Offline", tone: "border-scam/40 text-scam", dot: "bg-scam" },
}

/** A new message to the test inbox, prefilled: the code in the subject routes the result to this browser. */
function composeLinks(address: string, code: string | null) {
  const subject = code ? `${MAIL_SUBJECT} ${code}` : MAIL_SUBJECT
  const q = (k: string, v: string) => `${k}=${encodeURIComponent(v)}`
  return {
    mailto: `mailto:${address}?${q("subject", subject)}&${q("body", MAIL_BODY)}`,
    // Gmail web compose (tf=cm opens it); desktop only, mobile browsers land on the inbox
    gmail: `https://mail.google.com/mail/u/0/?${q("to", address)}&${q("su", subject)}&${q("body", MAIL_BODY)}&tf=cm`,
  }
}

/** The page header: what this is, how to use it, and one button that does the work. */
function TestHero({ address, code, state }: { address: string | null; code: string | null; state: HeroState }) {
  const links = address ? composeLinks(address, code) : null
  const pill = STATE_PILL[state]
  return (
    <PageHero
      title="Test the system"
      badge={
        <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10.5px] uppercase tracking-[0.14em]", pill.tone)}>
          <span className={cn("size-1.5 rounded-full", pill.dot)} aria-hidden="true" />
          {pill.text}
        </span>
      }
      note={
        <>
          <Lock className="size-3" aria-hidden="true" />
          Private to this browser
        </>
      }
      actions={
        <>
          <div className="flex flex-wrap gap-2">
            {links ? (
              <a href={links.mailto} className={HERO_PRIMARY} title="Opens a new message with the address and your private code filled in">
                <Send className="size-4" aria-hidden="true" />
                Send a test email
              </a>
            ) : (
              <span aria-disabled="true" className={cn(HERO_PRIMARY, "pointer-events-none opacity-40 shadow-none")}>
                <Send className="size-4" aria-hidden="true" />
                Send a test email
              </span>
            )}
            {links ? (
              <a href={links.gmail} target="_blank" rel="noopener noreferrer" className={cn(HERO_SECONDARY, "hidden sm:inline-flex")}>
                Gmail
                <ArrowUpRight className="size-4 text-lime" aria-hidden="true" />
              </a>
            ) : null}
          </div>
          <p className="font-mono text-[10.5px] text-faint">Address and your private code come filled in.</p>
        </>
      }
    >
      <ol aria-label="How it works" className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-2.5">
        {STEPS.map((step, i) => (
          <li key={step} className="flex items-center gap-2 text-sm">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-lime/40 font-mono text-[10px] font-bold text-lime">
              {i + 1}
            </span>
            {step}
            {i < STEPS.length - 1 ? <ChevronRight className="hidden size-3.5 text-faint sm:block" aria-hidden="true" /> : null}
          </li>
        ))}
      </ol>
    </PageHero>
  )
}

function Waiting() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      <span className="relative flex size-14 items-center justify-center">
        <span className="absolute inset-0 rounded-full border border-lime/30 [animation:aegis-pulse_2.4s_ease-in-out_infinite]" aria-hidden="true" />
        <span className="absolute inset-2 rounded-full border border-lime/20" aria-hidden="true" />
        <MailOpen className="size-5 text-lime" aria-hidden="true" />
      </span>
      <p className="label-mono text-[12px] text-muted-foreground">Waiting for mail</p>
      <p className="max-w-xs text-sm text-faint">Press Send a test email, paste a suspicious email and send. It appears here the moment it lands.</p>
    </div>
  )
}

function StageBar({ stages }: { stages: { name: string; status: string }[] }) {
  const byName = new Map(stages.map((s) => [s.name, s.status]))
  const finished = stages.filter((s) => s.status === "done" || s.status === "skipped").length
  return (
    <ol className="flex gap-1" aria-label={`${finished} of ${STAGES.length} stages finished`}>
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
  )
}

function statusLine(status: string, stages: { name: string; status: string }[], duration: number | null | undefined): string {
  if (status === "queued") return "Queued"
  if (status === "failed") return "Analysis failed"
  if (status === "running") return `Running ${stages.find((s) => s.status === "running")?.name ?? "pipeline"}`
  return `Analyzed${duration ? ` in ${seconds(duration)}` : ""}`
}

function InboxRow({ item, fresh, selected, onSelect }: { item: LiveInboxItem; fresh: boolean; selected: boolean; onSelect: () => void }) {
  const working = item.status === "queued" || item.status === "running"
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={cn(
          "flex w-full min-w-0 flex-col gap-2 rounded-xl border px-3 py-2.5 text-left transition-[background-color,border-color,box-shadow] duration-500",
          selected ? "border-lime/45 bg-lime/[0.06]" : "border-transparent hover:border-hair hover:bg-white/[0.03]",
          fresh && "border-lime/60 shadow-[0_0_24px_-6px_rgba(217,255,61,0.45)]",
        )}
      >
        <span className="flex min-w-0 items-start justify-between gap-2.5">
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-[13.5px] font-medium text-ink">{item.subject || "(no subject)"}</span>
            <span className="truncate font-mono text-[10.5px] text-faint">{[item.sender, timeAgo(item.created_at)].filter(Boolean).join(" · ")}</span>
          </span>
          {working ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-lime/30 px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-lime">
              <Loader2 className="size-3 animate-spin" aria-hidden="true" /> live
            </span>
          ) : (
            <VerdictBadge label={item.label} className="shrink-0" />
          )}
        </span>
        <StageBar stages={item.stages} />
        <span className="flex items-center justify-between gap-2 font-mono text-[10.5px] text-muted-foreground">
          <span className="truncate">{statusLine(item.status, item.stages, item.duration_s)}</span>
          {item.replied ? (
            <span className="inline-flex shrink-0 items-center gap-1 text-safe">
              <CheckCircle2 className="size-3" aria-hidden="true" /> replied
            </span>
          ) : null}
        </span>
      </button>
    </li>
  )
}

type Tab = "overview" | "flags" | "agents" | "email"

/** One email taken apart live (partially censored by the server): verdict strip, then tabs. */
function Dissection({ item, following, onFollow }: { item: LiveInboxItem; following: boolean; onFollow: () => void }) {
  const [detail, setDetail] = React.useState<LiveInboxDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [chosen, setChosen] = React.useState<Tab | null>(null)

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
        if (!alive) return
        setError(e instanceof Error ? e.message : "Could not open this email.")
        if (e instanceof ApiError && e.status === 404) return   // purged or gone: stop polling
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
  // While the agents run, show them; once there is a verdict, lead with it.
  const tab: Tab = chosen ?? (live ? "agents" : "overview")
  const label = detail?.verdict?.label ?? detail?.label ?? null
  const meta = label ? LABEL_META[label] : null
  const tabs: { id: Tab; text: string; count?: number }[] = [
    { id: "overview", text: "Overview" },
    { id: "flags", text: "Red flags", count: detail?.red_flags?.length },
    { id: "agents", text: "Agents" },
    { id: "email", text: "Email" },
  ]

  return (
    <>
      <header className="flex min-w-0 flex-col gap-3 border-b border-hair px-4 py-3.5 sm:px-5">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-display text-lg font-bold text-ink">{item.subject || "(no subject)"}</p>
            <p className="truncate font-mono text-[11px] text-faint">{[item.sender, timeAgo(item.created_at)].filter(Boolean).join(" · ")}</p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {following ? (
              <span className="hidden items-center gap-1.5 font-mono text-[10.5px] text-lime sm:inline-flex">
                <span className="size-1.5 rounded-full bg-lime [animation:aegis-pulse_2s_infinite]" aria-hidden="true" /> following newest
              </span>
            ) : (
              <button type="button" onClick={onFollow} className="font-mono text-[10.5px] text-muted-foreground hover:text-lime">
                Follow newest
              </button>
            )}
            {item.id ? (
              <Link href={`/cases/${encodeURIComponent(item.id)}`} className="inline-flex items-center gap-1 font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground hover:text-lime">
                Case <ArrowUpRight className="size-3.5" aria-hidden="true" />
              </Link>
            ) : null}
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-4">
          {detail && !live ? (
            <div className="flex shrink-0 flex-col items-center rounded-xl border border-hair bg-black/30 px-3.5 py-2">
              <span className="font-mono text-3xl font-semibold tabular-nums leading-none" style={{ color: meta?.color }}>
                {Math.round((detail.verdict?.score ?? detail.score ?? 0) * 100)}
              </span>
              <span className="label-mono mt-1 text-[9px]">risk</span>
            </div>
          ) : null}
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            {live ? (
              <p className="flex items-center gap-2 font-mono text-[12px] text-lime">
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                {detail ? statusLine(detail.status, detail.stages ?? [], null) : "Opening the email"}
              </p>
            ) : (
              <div className="flex flex-wrap items-center gap-2.5">
                <VerdictBadge label={label} />
                {detail?.verdict ? (
                  <span className="font-mono text-[11px] text-muted-foreground">
                    confidence {pct(detail.verdict.confidence)} · {statusLine(detail.status, detail.stages ?? [], detail.duration_s)}
                  </span>
                ) : null}
              </div>
            )}
            {!live && meta ? <p className={cn("font-display text-base font-bold leading-snug sm:text-lg", meta.tw)}>{meta.plain}</p> : null}
            <StageBar stages={detail?.stages ?? item.stages} />
          </div>
        </div>
      </header>

      <div role="tablist" aria-label="Dissection" className="flex gap-1 overflow-x-auto border-b border-hair px-3 py-2 sm:px-4">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setChosen(t.id)}
            className={cn(
              "shrink-0 rounded-full px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] transition-colors",
              tab === t.id ? "bg-lime text-black" : "text-muted-foreground hover:bg-white/[0.05] hover:text-ink",
            )}
          >
            {t.text}
            {t.count ? <span className={cn("ml-1.5", tab === t.id ? "text-black/60" : "text-faint")}>{t.count}</span> : null}
          </button>
        ))}
      </div>

      <div role="tabpanel" className="thin-scroll min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
        {!detail && error ? <ErrorState message={error} /> : null}
        {!detail && !error ? <LoadingState label="Opening the email" /> : null}
        {detail ? (
          tab === "overview" ? (
            <Overview detail={detail} live={live} />
          ) : tab === "flags" ? (
            <Flags detail={detail} live={live} />
          ) : tab === "agents" ? (
            <Agents stages={detail.stages ?? []} />
          ) : (
            <CensoredEmail detail={detail} />
          )
        ) : null}
      </div>
    </>
  )
}

function Pending({ live, children }: { live: boolean; children: React.ReactNode }) {
  return <p className="py-8 text-center text-sm text-faint">{live ? "The agents are still working. This fills in when they finish." : children}</p>
}

function Overview({ detail, live }: { detail: LiveInboxDetail; live: boolean }) {
  if (live) return <Pending live>{null}</Pending>
  if (detail.status === "failed") return <ErrorState message={detail.error || "The analysis failed. The pipeline fails closed, so treat this email as suspicious."} />
  return (
    <div className="flex flex-col gap-5">
      {detail.summary ? <p className="text-pretty text-[14.5px] leading-relaxed text-ink/85">{detail.summary}</p> : null}
      {detail.verdict?.corroboration?.length ? (
        <ul className="flex flex-wrap gap-2" aria-label="Independent sources that agree">
          {detail.verdict.corroboration.map((c) => (
            <li key={c} className="inline-flex items-center gap-1.5 rounded-full border border-hair bg-black/30 px-3 py-1 text-xs text-ink/85">
              <CheckCircle2 className="size-3.5 text-lime" aria-hidden="true" />
              {c}
            </li>
          ))}
        </ul>
      ) : null}
      {detail.actions?.length ? (
        <div>
          <p className="label-mono mb-2.5 text-ink/80">What to do next</p>
          <ol className="flex flex-col gap-2">
            {detail.actions.map((step, i) => (
              <li key={i} className="flex gap-3 text-[14px] leading-relaxed text-ink">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-lime font-mono text-[10px] font-bold text-black">{i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  )
}

function Flags({ detail, live }: { detail: LiveInboxDetail; live: boolean }) {
  if (!detail.red_flags?.length) return <Pending live={live}>No red flags were found in this email.</Pending>
  return (
    <ul className="flex flex-col divide-y divide-hair">
      {detail.red_flags.map((f, i) => (
        <li key={i} className="flex flex-col gap-1.5 py-3 first:pt-0">
          <span className="flex items-center gap-2">
            <SeverityPill severity={f.severity} />
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">{f.source}</span>
          </span>
          <p className="text-[14px] font-semibold leading-snug text-ink">{f.title}</p>
          {f.evidence ? <p className="break-words font-mono text-[12px] text-muted-foreground">&ldquo;{f.evidence}&rdquo;</p> : null}
        </li>
      ))}
    </ul>
  )
}

function Agents({ stages }: { stages: Stage[] }) {
  const byName = new Map(stages.map((s) => [s.name, s]))
  return (
    <ol className="flex flex-col divide-y divide-hair">
      {STAGES.map((name, i) => {
        const s = byName.get(name)
        const st = s?.status ?? "pending"
        return (
          <li key={name} className="flex min-w-0 items-start gap-3 py-2.5 first:pt-0">
            <span
              className={cn(
                "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border font-mono text-[10px]",
                st === "done" && "border-lime/50 text-lime",
                st === "running" && "border-lime text-lime [animation:aegis-pulse_1.2s_infinite]",
                st === "failed" && "border-scam/60 text-scam",
                (st === "skipped" || st === "pending") && "border-hair text-faint",
              )}
            >
              {i + 1}
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="flex items-center justify-between gap-2">
                <span className="font-mono text-[12px] font-semibold uppercase tracking-[0.1em] text-ink">{name}</span>
                <span className={cn("shrink-0 font-mono text-[11px]", st === "failed" ? "text-scam" : st === "running" ? "text-lime" : "text-faint")}>
                  {st === "done" ? seconds(s?.duration_s) : st}
                </span>
              </span>
              {s?.summary || s?.error ? <span className="mt-0.5 break-words text-[12.5px] text-muted-foreground">{s.error || s.summary}</span> : null}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function CensoredEmail({ detail }: { detail: LiveInboxDetail }) {
  const e = detail.email
  if (!e) return <Pending live={false}>No email content available.</Pending>
  const rows = (
    [
      ["From", e.from],
      ["Subject", e.subject],
    ] as [string, string | null | undefined][]
  ).filter((r): r is [string, string] => !!r[1])
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="inline-flex items-center gap-1.5 font-mono text-[10.5px] text-faint">
        <Lock className="size-3" aria-hidden="true" /> names, addresses and numbers partially censored
      </p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1">
        {rows.map(([k, v]) => (
          <React.Fragment key={k}>
            <dt className="label-mono pt-0.5 text-[9.5px]">{k}</dt>
            <dd className="break-words font-mono text-[12.5px] text-ink/90">{v}</dd>
          </React.Fragment>
        ))}
      </dl>
      {e.text ? (
        <pre className="whitespace-pre-wrap break-words rounded-lg border border-hair bg-black/30 p-3 font-mono text-[12px] leading-relaxed text-ink/80">{e.text}</pre>
      ) : null}
    </div>
  )
}
