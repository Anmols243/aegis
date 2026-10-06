import { DotPattern } from "@/components/ui/dot-pattern"

/**
 * App-wide background: a fixed dot pattern behind the page, brightest near the
 * top centre and fading out towards the edges.
 */
export function AppBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
      <DotPattern
        cx={1}
        cy={1}
        cr={1}
        className="fill-lime/25 [mask-image:radial-gradient(900px_circle_at_50%_30%,white,transparent)] md:fill-lime/25"
      />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_50%_35%,transparent_0%,rgba(10,12,14,0.55)_70%,rgba(10,12,14,0.85)_100%)]" />
    </div>
  )
}
