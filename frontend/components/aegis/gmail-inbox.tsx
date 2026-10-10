"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowUpRight, Loader2, Lock, Mail, MailOpen, RefreshCw, Unplug } from "lucide-react"
import { toast } from "sonner"

import { ErrorState, LoadingState, VerdictBadge } from "@/components/aegis/bits"
import { HERO_PRIMARY, HERO_SECONDARY, PageHero } from "@/components/aegis/page-hero"
import { VerdictReport } from "@/components/aegis/verdict-report"
import { api, ApiError, type Analysis, type AnalysisSummary, type Mailbox, type MailboxProvider } from "@/lib/api"
import { score100, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const POLL_MS = 3000
const DETAIL_POLL_MS = 1500

type Snapshot = { mailboxes: Mailbox[]; items: AnalysisSummary[] }

/**
 * Connected Gmail: the server checks the mailbox on its own every few seconds and analyzes new
 * mail; this page refreshes every 3 seconds and shows each email's verdict beside the list.
 */
export function GmailInbox() {
  const [snap, setSnap] = React.useState<Snapshot | null>(null)
  const [google, setGoogle] = React.useState<MailboxProvider | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [pinned, setPinned] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState<"connect" | "check" | "disconnect" | null>(null)
  const [refresh, setRefresh] = React.useState(0)
  // The sign-in callback returns to /inbox?signin=connected or ?signin_error=...
  const [signin] = React.useState(() => (typeof window === "undefined" ? null : new URLSearchParams(window.location.search)))

  React.useEffect(() => {
    if (!signin) return
    if (signin.get("signin") === "connected") toast.success("Gmail connected", { description: "AEGIS is reading your new mail now." })
    const err = signin.get("signin_error")
    if (err) toast.error(err)
    if (signin.has("signin") || err) window.history.replaceState(null, "", "/inbox")
  }, [signin])

  React.useEffect(() => {
    api
      .mailboxProviders()
      .then((ps) => setGoogle(ps.find((p) => p.id === "google") ?? null))
      .catch(() => setGoogle(null))
  }, [])

  React.useEffect(() => {
    let alive = true
    let timer = 0
    const tick = async () => {
      if (!document.hidden) {
        try {
          const [mailboxes, page] = await Promise.all([api.listMailboxes(), api.listAnalyses({ limit: 50, mine: true })])
          if (!alive) return
          setSnap({ mailboxes, items: page.items.filter((a) => a.source === "mailbox") })
          setError(null)
        } catch (e) {
          if (alive) setError(e instanceof Error ? e.message : "Could not load your inbox.")
        }
      }
      if (alive) timer = window.setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [refresh])

  const mailbox = snap?.mailboxes.find((m) => m.provider === "google") ?? snap?.mailboxes[0] ?? null
  const items = snap?.items ?? []
  const current = (pinned && items.find((i) => i.id === pinned)) || items[0] || null

  const connect = async () => {
    setBusy("connect")
    try {
      const r = await api.startOAuth("google")
      window.location.href = r.url
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not start Google sign-in.")
      setBusy(null)
    }
  }

  const check = async () => {
    if (!mailbox) return
    setBusy("check")
    try {
      await api.checkMailbox(mailbox.id)
      toast.success("Checking Gmail now")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not check the mailbox.")
    } finally {
      setBusy(null)
    }
  }

  const disconnect = async () => {
    if (!mailbox || !window.confirm(`Disconnect ${mailbox.email} from AEGIS? Its analyzed emails stay in your Cases.`)) return
    setBusy("disconnect")
    try {
      await api.removeMailbox(mailbox.id)
      toast.success("Gmail disconnected")
      setPinned(null)
      setRefresh((n) => n + 1)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not disconnect Gmail.")
    } finally {
      setBusy(null)
    }
  }

  const status = !snap ? "Connecting" : mailbox ? (mailbox.status === "error" ? "Needs attention" : mailbox.status === "paused" ? "Paused" : "Watching") : "Not connected"
  const tone = mailbox?.status === "error" ? "border-scam/40 text-scam" : mailbox && mailbox.status !== "paused" ? "border-lime/30 text-lime" : "border-hair text-muted-foreground"

  const hero = (
    <PageHero
      title="Your Gmail, checked for you"
      badge={
        <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10.5px] uppercase tracking-[0.14em]", tone)}>
          <span
            className={cn("size-1.5 rounded-full bg-current", status === "Watching" && "shadow-[0_0_10px_var(--aegis-lime)] [animation:aegis-pulse_2s_infinite]")}
            aria-hidden="true"
          />
          {status}
        </span>
      }
      note={
        <>
          <Lock className="size-3" aria-hidden="true" />
          Private to this browser
        </>
      }
      actions={
        mailbox ? (
          <>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void check()} disabled={!!busy} className={cn(HERO_PRIMARY, "disabled:opacity-50")}>
                {busy === "check" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
                Check now
              </button>
              <button type="button" onClick={() => void disconnect()} disabled={!!busy} className={cn(HERO_SECONDARY, "disabled:opacity-50")}>
                {busy === "disconnect" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Unplug className="size-4 text-lime" aria-hidden="true" />}
                Disconnect
              </button>
            </div>
            <p className="font-mono text-[10.5px] text-faint">
              {mailbox.email} · {mailbox.scanned} scanned · {mailbox.flagged} flagged
              {mailbox.last_checked_at ? ` · checked ${timeAgo(mailbox.last_checked_at)}` : ""}
            </p>
          </>
        ) : snap ? (
          <>
            <button type="button" onClick={() => void connect()} disabled={!!busy || !google?.supported} className={cn(HERO_PRIMARY, "disabled:opacity-40 disabled:shadow-none")}>
              {busy === "connect" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Mail className="size-4" aria-hidden="true" />}
              Connect Gmail
            </button>
            <p className="max-w-xs font-mono text-[10.5px] text-faint lg:text-right">
              {google?.supported ? "Read-only scan plus AEGIS labels. Disconnect any time." : "Google sign-in is not set up on this server yet (GOOGLE_CLIENT_ID)."}
            </p>
          </>
        ) : null
      }
    >
      Connect Gmail once. AEGIS checks it every few seconds, analyzes each new email with every agent, and labels scams in your inbox.
    </PageHero>
  )

  if (!snap) {
    return (
      <div className="flex flex-col gap-4">
        {hero}
        {error ? <ErrorState message={error} /> : <LoadingState label="Loading your inbox" />}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {hero}
      {mailbox?.last_error ? <ErrorState message={mailbox.last_error} /> : null}
      {mailbox || items.length ? (
        <div className="grid gap-4 lg:h-[calc(100dvh-20rem)] lg:min-h-[560px] lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
          <section aria-labelledby="mail-title" className="hud flex min-h-0 min-w-0 flex-col p-2">
            <div className="flex items-baseline justify-between gap-2 px-3 pb-2 pt-3">
              <h2 id="mail-title" className="label-mono text-ink/80">
                Inbox <span className="text-faint">{items.length}</span>
              </h2>
              <span className="font-mono text-[10.5px] text-faint">newest first</span>
            </div>
            {items.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                <MailOpen className="size-5 text-lime" aria-hidden="true" />
                <p className="label-mono text-[12px] text-muted-foreground">Waiting for mail</p>
                <p className="max-w-xs text-sm text-faint">New emails that reach your Gmail inbox appear here within seconds, analyzed.</p>
              </div>
            ) : (
              <ul className="thin-scroll flex max-h-[45vh] min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto px-1 pb-1 lg:max-h-none" aria-live="polite">
                {items.map((a) => (
                  <MailRow key={a.id} item={a} selected={current?.id === a.id} onSelect={() => setPinned(a.id === items[0]?.id ? null : a.id)} />
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Analysis" className="hud thin-scroll min-h-[480px] min-w-0 overflow-y-auto p-4 sm:p-5 lg:min-h-0">
            {current ? (
              <Detail key={current.id} id={current.id} />
            ) : (
              <p className="py-16 text-center text-sm text-faint">Select an email to see its verdict, evidence and what to do next.</p>
            )}
          </section>
        </div>
      ) : null}
    </div>
  )
}

function MailRow({ item, selected, onSelect }: { item: AnalysisSummary; selected: boolean; onSelect: () => void }) {
  const working = item.status === "queued" || item.status === "running"
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={cn(
          "flex w-full min-w-0 flex-col gap-1.5 rounded-xl border px-3 py-2.5 text-left transition-colors",
          selected ? "border-lime/45 bg-lime/[0.06]" : "border-transparent hover:border-hair hover:bg-white/[0.03]",
        )}
      >
        <span className="flex min-w-0 items-start justify-between gap-2.5">
          <span className="truncate text-[13.5px] font-medium text-ink">{item.subject || "(no subject)"}</span>
          {working ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-lime/30 px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-lime">
              <Loader2 className="size-3 animate-spin" aria-hidden="true" /> live
            </span>
          ) : (
            <VerdictBadge label={item.label} className="shrink-0" />
          )}
        </span>
        <span className="flex items-center justify-between gap-2 font-mono text-[10.5px] text-faint">
          <span className="truncate">{[item.sender, timeAgo(item.created_at)].filter(Boolean).join(" · ")}</span>
          {!working && item.score != null ? <span className="shrink-0 text-muted-foreground">risk {score100(item.score)}</span> : null}
        </span>
      </button>
    </li>
  )
}

/** One email's analysis: polls while the agents work, then shows the full verdict. */
function Detail({ id }: { id: string }) {
  const [a, setA] = React.useState<Analysis | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let alive = true
    let timer = 0
    const tick = async () => {
      try {
        const d = await api.analysis(id)
        if (!alive) return
        setA(d)
        setError(null)
        if (d.status === "done" || d.status === "failed") return
      } catch (e) {
        if (!alive) return
        setError(e instanceof Error ? e.message : "Could not open this email.")
        if (e instanceof ApiError && e.status === 404) return
      }
      if (alive) timer = window.setTimeout(tick, DETAIL_POLL_MS)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [id])

  if (!a) return error ? <ErrorState message={error} /> : <LoadingState label="Opening the email" />
  if (a.status === "queued" || a.status === "running") return <LoadingState label="The agents are working on it" />
  if (a.status === "failed") return <ErrorState message={a.error || "The analysis failed. The pipeline fails closed, so treat this email as suspicious."} />
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate font-display text-lg font-bold text-ink">{a.subject || a.email?.subject || "(no subject)"}</p>
        <Link href={`/cases/${encodeURIComponent(a.id)}`} className="inline-flex shrink-0 items-center gap-1 font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground hover:text-lime">
          Full case <ArrowUpRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>
      <VerdictReport analysis={a} />
    </div>
  )
}
