import type { Metadata } from "next"

import { RedteamArena } from "@/components/aegis/redteam-arena"

export const metadata: Metadata = { title: "Red-team arena" }

export default function RedteamPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-7 max-w-2xl">
        <p className="label-mono mb-2 text-lime">Red-team arena</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Attack AEGIS. Watch what gets through.</h1>
        <p className="mt-3 text-muted-foreground">
          Pick a real scam, let the mutation engine disguise it with homoglyphs, fresh domains, hidden links and prompt injection, and see which
          variants the pipeline still catches.
        </p>
      </div>
      <RedteamArena />
    </div>
  )
}
