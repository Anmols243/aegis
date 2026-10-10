"use client"

// Shown when Google or Microsoft returns to a different browser than the one where
// "Continue with Google" was clicked (for example AEGIS runs in an app's
// built-in browser and sign-in happened in the system browser). The mailbox is
// only attached after the person here confirms the code matches.

import * as React from "react"
import Link from "next/link"
import { CheckCircle2, Loader2, ShieldAlert } from "lucide-react"

import { ErrorState, LoadingState } from "@/components/aegis/bits"
import { api, ApiError, type SignInPairing } from "@/lib/api"

export function SignInConfirm({ state }: { state: string }) {
  const [pairing, setPairing] = React.useState<SignInPairing | null>(null)
  const [error, setError] = React.useState<string | null>(state ? null : "This link is incomplete. Start again from the Inbox page in AEGIS.")
  const [busy, setBusy] = React.useState<"connect" | "cancel" | null>(null)

  React.useEffect(() => {
    if (!state) return
    let alive = true
    api
      .signInPairing(state)
      .then((p) => alive && setPairing(p))
      .catch((e: unknown) => alive && setError(e instanceof ApiError || e instanceof Error ? e.message : "This sign-in is no longer valid."))
    return () => {
      alive = false
    }
  }, [state])

  const decide = async (connect: boolean) => {
    setBusy(connect ? "connect" : "cancel")
    try {
      const r = await api.signInConfirm(state, connect)
      setPairing((p) => (p ? { ...p, status: r.status } : p))
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "That did not work.")
    } finally {
      setBusy(null)
    }
  }

  if (error) return <div className="mt-6"><ErrorState message={error} /></div>
  if (!pairing) return <div className="mt-6"><LoadingState label="Checking the sign-in" /></div>

  if (pairing.status === "connected" || pairing.status === "cancelled") {
    const ok = pairing.status === "connected"
    return (
      <div className="hud mt-6 flex flex-col items-center gap-3 p-8 text-center">
        <CheckCircle2 className={ok ? "size-8 text-safe" : "size-8 text-faint"} aria-hidden="true" />
        <p className="text-lg font-semibold text-ink">{ok ? "Connected" : "Cancelled"}</p>
        <p className="text-sm text-muted-foreground">
          {ok
            ? "Go back to the AEGIS window you started from. It updates by itself. You can close this tab."
            : "Nothing was connected. You can close this tab."}
        </p>
      </div>
    )
  }

  if (pairing.status !== "confirm") return <div className="mt-6"><ErrorState message={pairing.error ?? "This sign-in is not waiting for confirmation."} /></div>

  return (
    <div className="hud mt-6 flex flex-col gap-5 p-6">
      <p className="text-sm text-muted-foreground">
        You signed in to {pairing.provider === "microsoft" ? "Microsoft" : "Google"} here, but AEGIS was opened in another window (often an app&apos;s built-in browser). Connect{" "}
        <span className="font-mono text-ink">{pairing.email}</span> to that window?
      </p>
      <div className="flex flex-col items-center gap-1 rounded-2xl border border-lime/25 bg-lime/5 py-5">
        <span className="label-mono text-[10px]">Code</span>
        <span className="font-mono text-4xl font-bold tracking-[0.3em] text-lime">{pairing.pair}</span>
        <span className="text-xs text-muted-foreground">It must match the code shown in your AEGIS window.</span>
      </div>
      <p className="flex items-start gap-2 text-xs text-faint">
        <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-susp" aria-hidden="true" />
        If you did not just click &quot;Continue with&quot; in AEGIS yourself, or someone sent you this link, press Cancel. Connecting gives that
        AEGIS window your mail&apos;s scan results.
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={!!busy}
          onClick={() => void decide(true)}
          className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-full bg-lime px-6 text-sm font-semibold text-black disabled:opacity-50"
        >
          {busy === "connect" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
          Codes match, connect
        </button>
        <button type="button" disabled={!!busy} onClick={() => void decide(false)} className="chip h-11 px-6">
          {busy === "cancel" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
          Cancel
        </button>
      </div>
      <Link href="/privacy" className="text-xs text-lime underline-offset-4 hover:underline">
        What AEGIS does with your mail
      </Link>
    </div>
  )
}
