import type { Metadata } from "next"

import { LiveInboxView } from "@/components/aegis/live-inbox"

export const metadata: Metadata = { title: "Live test inbox" }

export default function LivePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-7 max-w-2xl">
        <p className="label-mono mb-2 text-lime">Live test</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Email AEGIS. Watch it work.</h1>
        <p className="mt-3 text-muted-foreground">
          Send any email to the address below. AEGIS detects it as it arrives, runs every agent on it in front of you, and replies with an
          evidence-cited verdict.
        </p>
      </div>
      <LiveInboxView />
    </div>
  )
}
