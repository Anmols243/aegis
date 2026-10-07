import { LiquidMetal } from "@/components/ui/liquid-metal"

/**
 * App-wide background: a fixed liquid-chrome surface behind the page, toned
 * down and vignetted so panels and text stay readable. Ignores the pointer.
 */
export function AppBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
      <LiquidMetal intensity={0.45} />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_50%_35%,transparent_0%,rgba(10,12,14,0.55)_70%,rgba(10,12,14,0.85)_100%)]" />
    </div>
  )
}
