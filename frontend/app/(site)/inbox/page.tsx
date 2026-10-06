import type { Metadata } from "next"
import Link from "next/link"

import { InboxConnect } from "@/components/aegis/inbox-connect"
import { PrivacyPromises } from "@/components/aegis/privacy-promises"

export const metadata: Metadata = { title: "Connect your inbox" }

export default function InboxPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-8 max-w-2xl">
        <p className="label-mono mb-2 text-lime">Inbox</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Connect your inbox</h1>
        <p className="mt-3 text-muted-foreground">
          AEGIS checks every new email in the background and labels the scams for you, with the same evidence-cited verdict you get when you paste
          one in. Gmail, Yahoo, iCloud and most other providers work.
        </p>
      </div>

      <InboxConnect />

      <section aria-labelledby="privacy-heading" className="mt-14">
        <div className="mb-5 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="label-mono mb-2 text-lime">Privacy</p>
            <h2 id="privacy-heading" className="font-display text-2xl font-bold tracking-tight text-ink">
              Built to touch as little as possible
            </h2>
          </div>
          <Link href="/privacy" className="text-sm font-medium text-lime underline-offset-4 hover:underline">
            Read the privacy page
          </Link>
        </div>
        <PrivacyPromises />
      </section>
    </div>
  )
}
