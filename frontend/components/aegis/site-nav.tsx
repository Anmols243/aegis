"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

const LINKS = [
  { href: "/analyze", label: "Analyze" },
  { href: "/inbox", label: "Inbox" },
  { href: "/cases", label: "Cases" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/redteam", label: "Red team" },
]

export function SiteNav() {
  const pathname = usePathname()
  return (
    <header className="sticky top-0 z-40 border-b border-hair bg-[rgba(10,12,14,0.92)]">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-3 sm:gap-3 sm:px-6">
        <Link href="/" className="shrink-0 font-display text-[19px] font-extrabold tracking-tight text-ink sm:text-2xl">
          AEGIS<span className="text-lime">.</span>
        </Link>
        <nav aria-label="Main" className="ml-auto flex min-w-0 items-center gap-0.5 overflow-x-auto sm:gap-1">
          {LINKS.map((l) => {
            const active = pathname === l.href || pathname.startsWith(`${l.href}/`)
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-full px-1.5 py-1.5 font-mono text-[9.5px] font-semibold uppercase tracking-normal transition-colors sm:px-3.5 sm:text-xs sm:tracking-[0.12em]",
                  active ? "bg-lime text-black" : "text-muted-foreground hover:bg-white/5 hover:text-ink",
                )}
              >
                {l.label}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
