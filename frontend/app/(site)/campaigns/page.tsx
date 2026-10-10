import type { Metadata } from "next"
import { Network } from "lucide-react"

import { CampaignsView } from "@/components/aegis/campaigns-view"
import { PageHero } from "@/components/aegis/page-hero"

export const metadata: Metadata = { title: "Campaigns" }

export default function CampaignsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <PageHero className="mb-6" label="Threat graph" icon={Network} title="One scam is an email. Many are a campaign.">
        Emails that share senders, domains, links, phone numbers or message templates are linked. Clusters reveal the operation behind them.
      </PageHero>
      <CampaignsView />
    </div>
  )
}
