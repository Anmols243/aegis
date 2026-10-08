import type { Metadata } from "next"

import { LiveInboxView } from "@/components/aegis/live-inbox"

export const metadata: Metadata = { title: "Live test inbox" }

export default function LivePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">Email AEGIS. Watch it work.</h1>
        <p className="text-sm text-muted-foreground">Every agent runs live on the email you send, then the verdict is replied to you.</p>
      </div>
      <LiveInboxView />
    </div>
  )
}
