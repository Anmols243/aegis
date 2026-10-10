import * as React from "react"
import type { LucideIcon } from "lucide-react"

import { BorderBeam } from "@/components/ui/border-beam"
import { cn } from "@/lib/utils"

/** Lime filled call to action, as on the home page. */
export const HERO_PRIMARY =
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-lime px-7 text-sm font-semibold text-black shadow-[0_0_24px_rgba(217,255,61,0.35)] transition-transform active:scale-[0.98] sm:w-auto"
/** Dark outlined companion button. */
export const HERO_SECONDARY =
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-full border border-hair bg-surface/80 px-6 text-sm font-medium text-ink backdrop-blur transition-colors hover:border-lime/40 sm:w-auto"

/** The title with its closing mark in lime, like the AEGIS. wordmark (a lime period if it has none). */
function Accented({ text }: { text: string }) {
  const end = /[.?!]$/.test(text) ? text.length - 1 : text.length
  return (
    <>
      {text.slice(0, end)}
      <span className="text-lime">{text.slice(end) || "."}</span>
    </>
  )
}

/**
 * The page header used site-wide: a key panel (lime streak around the border, soft corner light)
 * with an eyebrow pill, a display title, a description and optional actions on the right.
 */
export function PageHero({
  label,
  icon: Icon,
  badge,
  note,
  title,
  accent = true,
  beam = true,
  children,
  actions,
  className,
}: {
  /** Section name in the eyebrow pill. */
  label?: string
  icon?: LucideIcon
  /** Replaces the eyebrow pill (the Live page shows its connection status there). */
  badge?: React.ReactNode
  /** Small mono note beside the pill, such as a privacy line. */
  note?: React.ReactNode
  title: string
  /** Lime closing mark; off for titles that quote an email subject. */
  accent?: boolean
  /** The moving lime streak; off where a panel below already has one (the verdict). */
  beam?: boolean
  children?: React.ReactNode
  actions?: React.ReactNode
  className?: string
}) {
  const panel = (
    <section aria-labelledby="page-title" className={cn("hud hud-glow px-5 pb-6 pt-5 sm:px-7 sm:py-6", !beam && className)}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between lg:gap-10">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {badge ?? (
              <span className="inline-flex items-center gap-2 rounded-full border border-lime/30 px-3 py-1 font-mono text-[10.5px] uppercase tracking-[0.14em] text-lime">
                {Icon ? <Icon className="size-3" aria-hidden="true" /> : null}
                {label}
              </span>
            )}
            {note ? <span className="label-mono inline-flex items-center gap-1.5">{note}</span> : null}
          </div>
          <h1 id="page-title" className="mt-3 text-balance break-words font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            {accent ? <Accented text={title} /> : title}
          </h1>
          {children ? <div className="mt-3 max-w-2xl text-pretty text-muted-foreground">{children}</div> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-col gap-2.5 lg:items-end">{actions}</div> : null}
      </div>
    </section>
  )
  if (!beam) return panel
  return (
    <BorderBeam className={cn("rounded-[1.25rem]", className)} radius={20} duration={9}>
      {panel}
    </BorderBeam>
  )
}
