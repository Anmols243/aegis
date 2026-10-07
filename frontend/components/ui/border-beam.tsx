"use client"

import * as React from "react"
import { animate, motion, useMotionValue, useReducedMotion, useTransform, type MotionValue } from "motion/react"

import { cn } from "@/lib/utils"

export interface BorderBeamProps extends React.ComponentProps<"div"> {
  /** Length of the light streak in CSS pixels. */
  size?: number
  /** Seconds for one full lap around the border. */
  duration?: number
  /** Start offset in seconds, so neighbouring beams do not move in lockstep. */
  delay?: number
  /** Streak tail color. */
  colorFrom?: string
  /** Streak head color. */
  colorTo?: string
  /** Border ring thickness in CSS pixels. */
  borderWidth?: number
  /** Corner radius the streak follows, in CSS pixels (match the wrapper's rounded class). */
  radius?: number
}

/** Stacked dashes that share a leading edge; shorter ones sit on top, so the streak brightens toward its head. */
const SEGMENTS = 6

/**
 * BorderBeam: wraps its children and sends a short lime streak around the
 * border at constant speed. The streak is a dash on an SVG rounded-rect
 * stroke, so it bends smoothly through the corners instead of rotating a
 * shape around them. Hidden under reduced motion.
 */
export function BorderBeam({
  size = 90,
  duration = 7,
  delay = 0,
  colorFrom = "#d9ff3d",
  colorTo = "#ffffff",
  borderWidth = 1,
  radius = 20,
  className,
  children,
  ...rest
}: BorderBeamProps) {
  const reduce = useReducedMotion()
  const ref = React.useRef<HTMLDivElement>(null)
  const [box, setBox] = React.useState<{ w: number; h: number } | null>(null)
  const progress = useMotionValue(0)
  const perimeter = useMotionValue(0)

  React.useEffect(() => {
    const el = ref.current
    if (!el || reduce) return
    const ro = new ResizeObserver(() => setBox({ w: el.offsetWidth, h: el.offsetHeight }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [reduce])

  React.useEffect(() => {
    if (reduce) return
    const controls = animate(progress, [0, 1], { duration, ease: "linear", repeat: Infinity, delay: -delay })
    return () => controls.stop()
  }, [progress, duration, delay, reduce])

  const inset = borderWidth / 2
  const w = box ? Math.max(0, box.w - borderWidth) : 0
  const h = box ? Math.max(0, box.h - borderWidth) : 0
  const r = Math.max(0, Math.min(radius - inset, w / 2, h / 2))
  const length = 2 * (w + h) - (8 - 2 * Math.PI) * r

  React.useEffect(() => {
    perimeter.set(length)
  }, [perimeter, length])

  return (
    <div ref={ref} data-slot="border-beam" className={cn("relative", className)} {...rest}>
      {children}
      {!reduce && box && length > size && (
        <svg aria-hidden="true" className="pointer-events-none absolute inset-0 z-[2] h-full w-full overflow-visible">
          {Array.from({ length: SEGMENTS }, (_, i) => {
            const share = (SEGMENTS - i) / SEGMENTS
            return (
              <BeamSegment
                key={i}
                progress={progress}
                perimeter={perimeter}
                dash={size * share}
                gap={length - size * share}
                color={i === SEGMENTS - 1 ? colorTo : colorFrom}
                opacity={i === SEGMENTS - 1 ? 1 : 0.25}
                x={inset}
                y={inset}
                w={w}
                h={h}
                r={r}
                strokeWidth={borderWidth}
              />
            )
          })}
        </svg>
      )}
    </div>
  )
}

function BeamSegment({
  progress,
  perimeter,
  dash,
  gap,
  color,
  opacity,
  x,
  y,
  w,
  h,
  r,
  strokeWidth,
}: {
  progress: MotionValue<number>
  perimeter: MotionValue<number>
  dash: number
  gap: number
  color: string
  opacity: number
  x: number
  y: number
  w: number
  h: number
  r: number
  strokeWidth: number
}) {
  // The dash's leading edge sits at progress * perimeter along the path. Dash plus gap equals the
  // perimeter, so the pattern repeats once per lap and the streak wraps across the path start.
  const offset = useTransform(() => dash - progress.get() * perimeter.get())
  return (
    <motion.rect
      x={x}
      y={y}
      width={w}
      height={h}
      rx={r}
      ry={r}
      fill="none"
      stroke={color}
      strokeOpacity={opacity}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeDasharray={`${dash} ${gap}`}
      strokeDashoffset={offset}
    />
  )
}

export default BorderBeam
