import { Cookie, EyeOff, KeyRound, Lock, MailCheck, MailOpen, Tag, Timer, Trash2, UserRoundX } from "lucide-react"

import { cn } from "@/lib/utils"

// Each promise maps to a guarantee in docs/API.md ("Privacy and viewers",
// "Mailboxes"). Do not add a promise here that the backend does not enforce.
export const PRIVACY_PROMISES = [
  {
    icon: MailOpen,
    title: "Read-only scan",
    text: "AEGIS reads new mail without marking it as read. Your inbox looks exactly as you left it.",
  },
  {
    icon: Tag,
    title: "Labels and flags only",
    text: "It adds an AEGIS label or flag to scams. It never moves, deletes, forwards or sends mail.",
  },
  {
    icon: MailCheck,
    title: "New mail only",
    text: "Scanning starts the moment you connect. Your existing mail is never read.",
  },
  {
    icon: KeyRound,
    title: "Encrypted app password",
    text: "Stored encrypted at rest (AES-256-GCM) and never shown again, not even to you.",
  },
  {
    icon: UserRoundX,
    title: "Your address stays out",
    text: "Your own email address is replaced with [your address] before any AI model sees the message.",
  },
  {
    icon: Timer,
    title: "Auto-deleted",
    text: "Email text is deleted after the retention period you choose (7 days by default). Only the verdict stays.",
  },
  {
    icon: EyeOff,
    title: "Private by default",
    text: "Your emails never appear in the public feed, the campaign graph, or anyone else's results.",
  },
  {
    icon: Trash2,
    title: "One-click disconnect",
    text: "Disconnecting deletes the stored password, and optionally every analysis from that mailbox.",
  },
  {
    icon: Cookie,
    title: "No tracking",
    text: "One functional cookie that remembers which results are yours. No analytics, no ads, no account.",
  },
] as const

export function PrivacyPromises({ compact = false, className }: { compact?: boolean; className?: string }) {
  const items = compact ? PRIVACY_PROMISES.slice(0, 6) : PRIVACY_PROMISES
  return (
    <ul className={cn("grid gap-3 sm:grid-cols-2", compact ? "lg:grid-cols-3" : "lg:grid-cols-3", className)}>
      {items.map((p) => (
        <li key={p.title} className="flex min-w-0 gap-3 rounded-2xl border border-hair bg-surface/70 p-4">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-lime/25 bg-lime/5 text-lime">
            <p.icon className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">{p.title}</p>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{p.text}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function PrivateBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border border-hair px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground",
        className,
      )}
      title="Private: unlisted, only people with the link can see it"
    >
      <Lock className="size-3" aria-hidden="true" />
      Private
    </span>
  )
}
