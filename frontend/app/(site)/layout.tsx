import Link from "next/link"

import { SiteNav } from "@/components/aegis/site-nav"

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteNav />
      <main className="flex-1">{children}</main>
      <footer className="border-t border-hair">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-faint sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span className="font-mono uppercase tracking-[0.14em]">AEGIS · ForgeHacks 2026 · AI + Cybersecurity</span>
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>
              Every claim in a verdict cites the evidence it came from.{" "}
              <Link href="/analyze" className="text-lime underline-offset-4 hover:underline">
                Analyze an email
              </Link>
            </span>
            <Link href="/privacy" className="text-muted-foreground underline-offset-4 hover:text-ink hover:underline">
              Privacy
            </Link>
          </span>
        </div>
      </footer>
    </>
  )
}
