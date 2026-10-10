import type { Metadata } from "next"
import { Swords } from "lucide-react"

import { PageHero } from "@/components/aegis/page-hero"
import { RedteamArena } from "@/components/aegis/redteam-arena"

export const metadata: Metadata = { title: "Red-team arena" }

export default function RedteamPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <PageHero className="mb-6" label="Red-team arena" icon={Swords} title="Attack AEGIS. Watch what gets through.">
        Pick a real scam, let the mutation engine disguise it with homoglyphs, fresh domains, hidden links and prompt injection, and see which variants
        the pipeline still catches.
      </PageHero>
      <RedteamArena />
    </div>
  )
}
