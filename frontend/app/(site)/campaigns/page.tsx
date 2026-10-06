import type { Metadata } from "next"

import { CampaignsView } from "@/components/aegis/campaigns-view"

export const metadata: Metadata = { title: "Campaigns" }

export default function CampaignsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-7 max-w-2xl">
        <p className="label-mono mb-2 text-lime">Threat graph</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">One scam is an email. Many are a campaign.</h1>
        <p className="mt-3 text-muted-foreground">
          Emails that share senders, domains, links, phone numbers or message templates are linked. Clusters reveal the operation behind them.
        </p>
      </div>
      <CampaignsView />
    </div>
  )
}
