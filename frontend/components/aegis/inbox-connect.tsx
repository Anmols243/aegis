"use client"

import * as React from "react"
import Link from "next/link"
import { CheckCircle2, ExternalLink, Loader2, Mail, Pause, Play, RefreshCw, ShieldAlert, Unplug } from "lucide-react"
import { toast } from "sonner"

import { ErrorState, LoadingState, SectionTitle } from "@/components/aegis/bits"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { api, ApiError, type Mailbox, type MailboxProvider } from "@/lib/api"
import { timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const RETENTION = [1, 7, 30] as const

const STATUS_META: Record<string, { text: string; cls: string }> = {
  active: { text: "Active", cls: "border-safe/40 text-safe" },
  paused: { text: "Paused", cls: "border-hair text-muted-foreground" },
  error: { text: "Error", cls: "border-scam/40 text-scam" },
}

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : fallback
}

export function InboxConnect() {
  const [providers, setProviders] = React.useState<MailboxProvider[] | null>(null)
  const [mailboxes, setMailboxes] = React.useState<Mailbox[] | null>(null)
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
    return () => {
      alive = false
    }
  }, [attempt])

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
      <ConnectForm providers={providers} onConnected={(m) => setMailboxes((prev) => [m, ...(prev ?? []).filter((x) => x.id !== m.id)])} />
      <section aria-labelledby="connected-heading" className="flex min-w-0 flex-col gap-3">
        <SectionTitle>
          <span id="connected-heading">Connected to this browser</span>
        </SectionTitle>
        {mailboxes.length === 0 ? (
          <div className="hud flex flex-col items-center gap-2 px-6 py-10 text-center">
            <Mail className="size-6 text-faint" aria-hidden="true" />
            <p className="label-mono text-[12px] text-muted-foreground">No mailbox connected</p>
            <p className="max-w-sm text-sm text-faint">Connect one on the left. New mail will be checked about once a minute.</p>
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

function ConnectForm({ providers, onConnected }: { providers: MailboxProvider[]; onConnected: (m: Mailbox) => void }) {
  const firstSupported = providers.find((p) => p.supported)?.id ?? ""
  const [providerId, setProviderId] = React.useState(firstSupported)
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [host, setHost] = React.useState("")
  const [retention, setRetention] = React.useState<number>(7)
  const [consent, setConsent] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const provider = providers.find((p) => p.id === providerId) ?? null
  const isCustom = providerId === "custom"
  const canSubmit = !!provider?.supported && email.includes("@") && password.length > 0 && consent && (!isCustom || host.trim().length > 0) && !busy

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      const m = await api.connectMailbox({
        provider: providerId,
        email: email.trim(),
        app_password: password,
        host: isCustom ? host.trim() : undefined,
        retention_days: retention,
      })
      setPassword("")
      setConsent(false)
      onConnected(m)
      toast.success("Mailbox connected", { description: "New mail will be checked about once a minute." })
    } catch (err) {
      setError(errorText(err, "Could not connect the mailbox."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="hud flex min-w-0 flex-col gap-5 p-5 sm:p-6" aria-describedby="connect-help">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight text-ink">Connect a mailbox</h2>
        <p id="connect-help" className="mt-1 text-sm text-muted-foreground">
          Uses an app password over IMAP. Your normal password never leaves you.
        </p>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="label-mono mb-2 text-[11px]">1. Provider</legend>
        <div className="flex flex-wrap gap-2">
          {providers.map((p) => (
            <button
              key={p.id}
              type="button"
              className="chip disabled:cursor-not-allowed disabled:opacity-40"
              data-active={providerId === p.id}
              aria-pressed={providerId === p.id}
              disabled={!p.supported}
              title={p.supported ? undefined : (p.reason ?? "Not supported yet")}
              onClick={() => {
                setProviderId(p.id)
                setError(null)
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
        {providers.some((p) => !p.supported) ? (
          <ul className="mt-1 flex flex-col gap-1">
            {providers
              .filter((p) => !p.supported)
              .map((p) => (
                <li key={p.id} className="text-xs text-faint">
                  {p.name}: {p.reason ?? "not supported yet"}
                </li>
              ))}
          </ul>
        ) : null}
      </fieldset>

      {provider && provider.steps.length > 0 ? (
        <div className="rounded-2xl border border-hair bg-black/30 p-4">
          <p className="label-mono mb-2 text-[11px]">2. Create an app password</p>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-[13px] leading-relaxed text-muted-foreground marker:text-lime">
            {provider.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          {provider.app_password_url ? (
            <a
              href={provider.app_password_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-lime underline-offset-4 hover:underline"
            >
              Open {provider.name} app passwords <ExternalLink className="size-3.5" aria-hidden="true" />
            </a>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col gap-3">
        <p className="label-mono text-[11px]">3. Sign in</p>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground">Email address</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="h-11 rounded-xl border border-hair bg-surface px-3.5 font-mono text-[13px] text-ink placeholder:text-faint focus:border-lime/50 focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground">App password (not your normal password)</span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="16-character app password"
            className="h-11 rounded-xl border border-hair bg-surface px-3.5 font-mono text-[13px] text-ink placeholder:text-faint focus:border-lime/50 focus:outline-none"
          />
        </label>
        {isCustom ? (
          <label className="flex flex-col gap-1.5">
            <span className="text-xs text-muted-foreground">IMAP server (port 993, TLS)</span>
            <input
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="imap.example.com"
              className="h-11 rounded-xl border border-hair bg-surface px-3.5 font-mono text-[13px] text-ink placeholder:text-faint focus:border-lime/50 focus:outline-none"
            />
          </label>
        ) : null}
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="label-mono mb-2 text-[11px]">4. Keep email text for</legend>
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

      {error ? (
        <p role="alert" className="flex items-start gap-2 rounded-xl border border-scam/30 bg-scam/5 px-3.5 py-2.5 text-sm text-ink">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-scam" aria-hidden="true" />
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={!canSubmit}
        className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-lime px-7 text-sm font-semibold text-black shadow-[0_0_24px_rgba(217,255,61,0.3)] transition-transform active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
      >
        {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Mail className="size-4" aria-hidden="true" />}
        {busy ? "Checking the login" : "Connect mailbox"}
      </button>
    </form>
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
            {m.host} · {m.label_mode === "gmail-labels" ? "Gmail labels" : "IMAP flags"} · keeps text {m.retention_days}d
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
            <DialogDescription>AEGIS stops checking this mailbox and deletes the stored app password right away.</DialogDescription>
          </DialogHeader>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-hair bg-black/20 p-3.5">
            <input type="checkbox" checked={purge} onChange={(e) => setPurge(e.target.checked)} className="mt-0.5 size-4 shrink-0 accent-[var(--aegis-lime)]" />
            <span className="text-sm text-ink">Also delete all analyses from this mailbox</span>
          </label>
          <p className="text-xs text-faint">
            To stop access completely, also revoke the app password in your {m.provider === "custom" ? "provider" : m.provider} account settings.
          </p>
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
