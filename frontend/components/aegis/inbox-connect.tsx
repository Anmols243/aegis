"use client"

import * as React from "react"
import Link from "next/link"
import { CheckCircle2, Copy, ExternalLink, Forward, Loader2, Mail, Pause, Play, RefreshCw, ShieldAlert, Unplug } from "lucide-react"
import { toast } from "sonner"

import { ErrorState, LoadingState, SectionTitle } from "@/components/aegis/bits"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { api, ApiError, type Mailbox, type MailboxProvider, type SignIn, type SignInStatus } from "@/lib/api"
import { timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const RETENTION = [1, 7, 30] as const

const STATUS_META: Record<string, { text: string; cls: string }> = {
  active: { text: "Active", cls: "border-safe/40 text-safe" },
  paused: { text: "Paused", cls: "border-hair text-muted-foreground" },
  error: { text: "Error", cls: "border-scam/40 text-scam" },
}

const PROVIDER_META: Record<string, { name: string; tags: string }> = {
  google: { name: "Google", tags: "Gmail labels" },
  microsoft: { name: "Microsoft", tags: "Outlook categories" },
}

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : fallback
}

export function InboxConnect() {
  const [providers, setProviders] = React.useState<MailboxProvider[] | null>(null)
  const [mailboxes, setMailboxes] = React.useState<Mailbox[] | null>(null)
  const [inboxAddress, setInboxAddress] = React.useState<string | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)

  const refreshMailboxes = React.useCallback(async () => {
    try {
      setMailboxes(await api.mailboxes())
    } catch (e) {
      setLoadError(errorText(e, "Could not load your mailboxes."))
    }
  }, [])

  React.useEffect(() => {
    let alive = true
    Promise.all([api.mailboxProviders(), api.mailboxes()])
      .then(([p, m]) => {
        if (!alive) return
        setProviders(p)
        setMailboxes(m)
        setLoadError(null)
      })
      .catch((e: unknown) => alive && setLoadError(errorText(e, "Could not load the inbox settings.")))
    api
      .publicConfig()
      .then((c) => alive && setInboxAddress(c.inbox_address))
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [attempt])

  // Back from a same-browser sign-in: report the outcome once, then tidy the URL.
  React.useEffect(() => {
    const q = new URLSearchParams(window.location.search)
    const ok = q.get("signin") === "connected"
    const err = q.get("signin_error")
    if (!ok && !err) return
    if (ok) toast.success("Mailbox connected", { description: "New mail will be checked about once a minute." })
    else toast.error("Sign-in did not finish", { description: err?.slice(0, 200) })
    window.history.replaceState(null, "", window.location.pathname)
  }, [])

  // Keep status and counts fresh while the page is open.
  React.useEffect(() => {
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") void refreshMailboxes()
    }, 15000)
    return () => window.clearInterval(t)
  }, [refreshMailboxes])

  if (loadError && !providers) return <ErrorState message={loadError} onRetry={() => setAttempt((n) => n + 1)} />
  if (!providers || !mailboxes) return <LoadingState label="Loading inbox settings" />

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start">
      <ConnectForm providers={providers} inboxAddress={inboxAddress} onConnected={() => void refreshMailboxes()} />
      <section aria-labelledby="connected-heading" className="flex min-w-0 flex-col gap-3">
        <SectionTitle>
          <span id="connected-heading">Connected to this browser</span>
        </SectionTitle>
        {mailboxes.length === 0 ? (
          <div className="hud flex flex-col items-center gap-2 px-6 py-10 text-center">
            <Mail className="size-6 text-faint" aria-hidden="true" />
            <p className="label-mono text-[12px] text-muted-foreground">No mailbox connected</p>
            <p className="max-w-sm text-sm text-faint">Sign in on the left. New mail will be checked about once a minute.</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {mailboxes.map((m) => (
              <MailboxCard
                key={m.id}
                mailbox={m}
                onChange={(next) => setMailboxes((prev) => (prev ?? []).map((x) => (x.id === next.id ? next : x)))}
                onRemoved={() => setMailboxes((prev) => (prev ?? []).filter((x) => x.id !== m.id))}
                onRefresh={refreshMailboxes}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-[18px]" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

function MicrosoftMark() {
  return (
    <svg viewBox="0 0 21 21" className="size-[17px]" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  )
}

const MARKS: Record<string, () => React.JSX.Element> = { google: GoogleMark, microsoft: MicrosoftMark }

// Sign-in opens in a new tab through a real link. Inside an app's built-in
// browser panel (where Google refuses to sign in) the host hands that link to
// the system browser; the sign-in then finishes there and this window learns
// the outcome by polling. A copyable link covers hosts that do neither.
function SignInPanel({
  providers,
  retention,
  consent,
  onConnected,
}: {
  providers: MailboxProvider[]
  retention: number
  consent: boolean
  onConnected: () => void
}) {
  const ready = providers.filter((p) => p.supported)
  // `key` ties prepared sign-ins (or the error) to the retention they were made for.
  const [prepared, setPrepared] = React.useState<{ key: number; byProvider: Record<string, SignIn> } | null>(null)
  const [prepareError, setPrepareError] = React.useState<{ key: number; msg: string } | null>(null)
  const [waiting, setWaiting] = React.useState<(SignIn & { provider: string }) | null>(null)
  const [status, setStatus] = React.useState<SignInStatus | null>(null)
  const [failure, setFailure] = React.useState<string | null>(null)
  const signIns = prepared && prepared.key === retention ? prepared.byProvider : null
  const error = failure ?? (prepareError && prepareError.key === retention ? prepareError.msg : null)
  const readyIds = ready.map((p) => p.id).join(",")

  // A started sign-in is valid for 10 minutes, so prepare them as soon as the
  // user has agreed; the buttons can then be plain links (no popup blocker).
  React.useEffect(() => {
    if (!consent || waiting || !readyIds) return
    let alive = true
    const ids = readyIds.split(",")
    Promise.all(ids.map((id) => api.signIn(id, retention)))
      .then((list) => alive && setPrepared({ key: retention, byProvider: Object.fromEntries(ids.map((id, i) => [id, list[i]])) }))
      .catch((e: unknown) => alive && setPrepareError({ key: retention, msg: errorText(e, "Could not start the sign-in.") }))
    return () => {
      alive = false
    }
  }, [consent, retention, waiting, readyIds])

  React.useEffect(() => {
    if (!waiting) return
    let alive = true
    const tick = async () => {
      try {
        const s = await api.signInStatus(waiting.state)
        if (!alive) return
        setStatus(s)
        if (s.status === "connected") {
          toast.success("Mailbox connected", { description: `${s.email ?? "Your mailbox"} will be checked about once a minute.` })
          setWaiting(null)
          setStatus(null)
          onConnected()
        } else if (s.status === "error" || s.status === "cancelled" || s.status === "expired") {
          setFailure(s.status === "cancelled" ? "The sign-in was cancelled." : s.status === "expired" ? "The sign-in expired. Please try again." : (s.error ?? "Sign-in failed."))
          setWaiting(null)
          setStatus(null)
        }
      } catch {
        // transient: keep polling
      }
    }
    const t = window.setInterval(() => void tick(), 2000)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [waiting, onConnected])

  const copyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      toast.success("Link copied", { description: "Paste it into Chrome, Edge, Firefox or Safari." })
    } catch {
      toast.error("Could not copy. Use Open again instead.")
    }
  }

  if (ready.length === 0) {
    return <p className="text-sm text-faint">Mailbox sign-in is not set up on this server yet.</p>
  }

  if (waiting) {
    const confirming = status?.status === "confirm" || status?.status === "saving"
    const name = PROVIDER_META[waiting.provider]?.name ?? waiting.provider
    return (
      <div className="flex flex-col gap-3 rounded-2xl border border-lime/25 bg-lime/5 p-4" role="status" aria-live="polite">
        <div className="flex items-start gap-3">
          <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-lime" aria-hidden="true" />
          <div className="min-w-0 text-sm text-ink">
            {confirming ? (
              <>
                Almost done. In the browser where you signed in, check the code matches and press <strong>Connect</strong>
                {status?.email ? (
                  <>
                    {" "}
                    for <span className="font-mono">{status.email}</span>
                  </>
                ) : null}
                .
              </>
            ) : (
              `Finish signing in in the ${name} tab. This page updates by itself.`
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="label-mono text-[10px]">Your code</span>
          <span className="font-mono text-2xl font-bold tracking-[0.3em] text-lime">{waiting.pair}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a href={waiting.url} target="_blank" rel="noopener noreferrer" className="chip inline-flex items-center gap-1.5">
            <ExternalLink className="size-3.5" aria-hidden="true" /> Open {name} again
          </a>
          <button type="button" className="chip inline-flex items-center gap-1.5" onClick={() => void copyLink(waiting.url)}>
            <Copy className="size-3.5" aria-hidden="true" /> Copy link
          </button>
          <button
            type="button"
            className="ml-auto text-xs text-faint hover:text-ink"
            onClick={() => {
              setWaiting(null)
              setStatus(null)
            }}
          >
            Cancel
          </button>
        </div>
        <p className="text-xs text-faint">
          Google blocks sign-in inside some apps&apos; built-in browsers (&quot;This browser or app may not be secure&quot;). If that happens, copy the link
          into your normal browser.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2.5">
      {ready.map((p) => {
        const s = consent && signIns ? signIns[p.id] : undefined
        const Mark = MARKS[p.id] ?? (() => <Mail className="size-4" aria-hidden="true" />)
        return (
          <a
            key={p.id}
            href={s?.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-disabled={!s}
            title={p.covers}
            onClick={(e) => {
              if (!s) {
                e.preventDefault()
                return
              }
              setFailure(null)
              setPrepared(null)
              setWaiting({ ...s, provider: p.id })
            }}
            className={cn(
              "inline-flex h-12 items-center justify-center gap-3 rounded-full border border-[#dadce0] bg-white px-7 text-sm font-semibold text-[#1f1f1f] transition-transform active:scale-[0.98]",
              !s && "pointer-events-none cursor-not-allowed opacity-40",
            )}
          >
            {consent && !s && !error ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Mark />}
            Continue with {p.name}
          </a>
        )
      })}
      <p className="text-center text-xs text-faint">
        {consent
          ? "Opens in a new tab. You allow AEGIS to read new mail and tag it; it never sends, moves or deletes."
          : "Tick the box above first."}
      </p>
      {ready.length < providers.length ? (
        <p className="text-center text-xs text-faint">
          {providers
            .filter((p) => !p.supported)
            .map((p) => p.name)
            .join(", ")}{" "}
          sign-in is not set up on this server yet.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="flex items-start gap-2 rounded-xl border border-scam/30 bg-scam/5 px-3.5 py-2.5 text-sm text-ink">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-scam" aria-hidden="true" />
          {error}
        </p>
      ) : null}
    </div>
  )
}

function ConnectForm({ providers, inboxAddress, onConnected }: { providers: MailboxProvider[]; inboxAddress: string | null; onConnected: () => void }) {
  const [retention, setRetention] = React.useState<number>(7)
  const [consent, setConsent] = React.useState(false)

  return (
    <div className="hud flex min-w-0 flex-col gap-5 p-5 sm:p-6">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight text-ink">Connect a mailbox</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Sign in with your email provider. Your password never reaches AEGIS, and you can remove access any time.
        </p>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="label-mono mb-2 text-[11px]">Keep email text for</legend>
        <div className="flex flex-wrap gap-2">
          {RETENTION.map((d) => (
            <button key={d} type="button" className="chip" data-active={retention === d} aria-pressed={retention === d} onClick={() => setRetention(d)}>
              {d} {d === 1 ? "day" : "days"}
            </button>
          ))}
        </div>
        <p className="text-xs text-faint">After that the email text is deleted. The verdict stays so your history still makes sense.</p>
      </fieldset>

      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-hair bg-surface/60 p-4">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--aegis-lime)]"
        />
        <span className="text-sm text-ink">
          I understand new emails will be sent to the AI models for analysis.{" "}
          <Link href="/privacy" className="text-lime underline-offset-4 hover:underline">
            What exactly is shared
          </Link>
        </span>
      </label>

      <SignInPanel providers={providers} retention={retention} consent={consent} onConnected={onConnected} />

      <div className="flex items-start gap-3 rounded-2xl border border-hair bg-black/30 p-4">
        <Forward className="mt-0.5 size-4 shrink-0 text-lime" aria-hidden="true" />
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          Yahoo, iCloud or another provider? Those do not offer a sign-in that lets apps read mail. Forward a suspicious email to{" "}
          {inboxAddress ? <span className="break-all font-mono text-ink">{inboxAddress}</span> : "the AEGIS inbox"} and the verdict comes back as a
          reply, or{" "}
          <Link href="/analyze" className="text-lime underline-offset-4 hover:underline">
            paste it here
          </Link>
          .
        </p>
      </div>
    </div>
  )
}

function MailboxCard({
  mailbox: m,
  onChange,
  onRemoved,
  onRefresh,
}: {
  mailbox: Mailbox
  onChange: (m: Mailbox) => void
  onRemoved: () => void
  onRefresh: () => Promise<void>
}) {
  const [busy, setBusy] = React.useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = React.useState(false)
  const [purge, setPurge] = React.useState(true)
  const status = STATUS_META[m.status] ?? STATUS_META.paused

  const run = async (name: string, fn: () => Promise<void>) => {
    setBusy(name)
    try {
      await fn()
    } catch (e) {
      toast.error(errorText(e, "That did not work."))
    } finally {
      setBusy(null)
    }
  }

  return (
    <li className="hud flex min-w-0 flex-col gap-3 p-4 sm:p-5">
      <div className="flex min-w-0 items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-lime/25 bg-lime/5 text-lime">
          <Mail className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-[13px] font-semibold text-ink">{m.email}</p>
          <p className="mt-0.5 truncate font-mono text-[11px] text-faint">
            Signed in with {PROVIDER_META[m.provider]?.name ?? m.provider} · {PROVIDER_META[m.provider]?.tags ?? "tags"} · keeps text {m.retention_days}d
          </p>
        </div>
        <span className={cn("shrink-0 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em]", status.cls)}>{status.text}</span>
      </div>

      <dl className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl border border-hair bg-black/20 px-2 py-2">
          <dt className="label-mono text-[9.5px]">Scanned</dt>
          <dd className="font-mono text-lg font-semibold tabular-nums text-ink">{m.scanned}</dd>
        </div>
        <div className="rounded-xl border border-hair bg-black/20 px-2 py-2">
          <dt className="label-mono text-[9.5px]">Flagged</dt>
          <dd className="font-mono text-lg font-semibold tabular-nums text-scam">{m.flagged}</dd>
        </div>
        <div className="rounded-xl border border-hair bg-black/20 px-2 py-2">
          <dt className="label-mono text-[9.5px]">Checked</dt>
          <dd className="truncate pt-1 font-mono text-[12px] text-ink">{m.last_checked_at ? timeAgo(m.last_checked_at) : "not yet"}</dd>
        </div>
      </dl>

      {m.last_error ? (
        <p role="status" className="rounded-xl border border-scam/30 bg-scam/5 px-3 py-2 text-xs text-ink">
          {m.last_error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="chip inline-flex items-center gap-1.5"
          disabled={!!busy || m.status === "paused"}
          onClick={() =>
            run("check", async () => {
              await api.checkMailbox(m.id)
              toast.success("Checking for new mail")
              window.setTimeout(() => void onRefresh(), 4000)
            })
          }
        >
          {busy === "check" ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" aria-hidden="true" />}
          Check now
        </button>
        {m.status === "paused" ? (
          <button type="button" className="chip inline-flex items-center gap-1.5" disabled={!!busy} onClick={() => run("resume", async () => onChange(await api.resumeMailbox(m.id)))}>
            {busy === "resume" ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" aria-hidden="true" />}
            Resume
          </button>
        ) : (
          <button type="button" className="chip inline-flex items-center gap-1.5" disabled={!!busy} onClick={() => run("pause", async () => onChange(await api.pauseMailbox(m.id)))}>
            {busy === "pause" ? <Loader2 className="size-3.5 animate-spin" /> : <Pause className="size-3.5" aria-hidden="true" />}
            Pause
          </button>
        )}
        <button type="button" className="chip inline-flex items-center gap-1.5" disabled={!!busy} onClick={() => setConfirmOpen(true)}>
          <Unplug className="size-3.5" aria-hidden="true" />
          Disconnect
        </button>
        <Link href="/cases?mine=true" className="ml-auto text-xs font-medium text-lime underline-offset-4 hover:underline">
          See my results
        </Link>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="border-hair bg-surface">
          <DialogHeader>
            <DialogTitle className="font-display">Disconnect {m.email}?</DialogTitle>
            <DialogDescription>
              {m.provider === "google"
                ? "AEGIS stops checking this mailbox, deletes its Google access and revokes it at Google right away."
                : "AEGIS stops checking this mailbox and deletes its stored access right away."}
            </DialogDescription>
          </DialogHeader>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-hair bg-black/20 p-3.5">
            <input type="checkbox" checked={purge} onChange={(e) => setPurge(e.target.checked)} className="mt-0.5 size-4 shrink-0 accent-[var(--aegis-lime)]" />
            <span className="text-sm text-ink">Also delete all analyses from this mailbox</span>
          </label>
          {m.provider !== "google" && m.manage_url ? (
            <p className="text-xs text-faint">
              Microsoft has no way for an app to give its access back, so also remove AEGIS under{" "}
              <a href={m.manage_url} target="_blank" rel="noopener noreferrer" className="text-lime underline-offset-4 hover:underline">
                your account&apos;s app permissions
              </a>
              .
            </p>
          ) : null}
          <DialogFooter className="gap-2">
            <button type="button" className="chip" onClick={() => setConfirmOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              disabled={!!busy}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-full bg-scam px-5 text-sm font-semibold text-black disabled:opacity-50"
              onClick={() =>
                run("disconnect", async () => {
                  await api.disconnectMailbox(m.id, purge)
                  setConfirmOpen(false)
                  onRemoved()
                  toast.success(purge ? "Disconnected and deleted" : "Disconnected", {
                    icon: <CheckCircle2 className="size-4" aria-hidden="true" />,
                  })
                })
              }
            >
              {busy === "disconnect" ? <Loader2 className="size-4 animate-spin" /> : null}
              Disconnect
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  )
}
