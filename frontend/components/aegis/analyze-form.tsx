"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, FileUp, Loader2, X } from "lucide-react"
import { toast } from "sonner"

import { VerdictBadge } from "@/components/aegis/bits"
import { BorderBeam } from "@/components/ui/border-beam"
import { api, ApiError, type Sample } from "@/lib/api"
import { cn } from "@/lib/utils"

const MAX_BYTES = 2 * 1024 * 1024

export function AnalyzeForm() {
  const router = useRouter()
  const [raw, setRaw] = React.useState("")
  const [file, setFile] = React.useState<File | null>(null)
  const [dragging, setDragging] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [samples, setSamples] = React.useState<Sample[] | null>(null)
  const [samplesFailed, setSamplesFailed] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    api
      .samples()
      .then(setSamples)
      .catch(() => setSamplesFailed(true))
  }, [])

  const pickFile = (f: File | undefined | null) => {
    if (!f) return
    if (f.size > MAX_BYTES) {
      setError("That file is larger than 2 MB. Export just the one message as .eml.")
      return
    }
    setError(null)
    setFile(f)
  }

  const submit = async (override?: string) => {
    const text = override ?? raw
    if (!file && !text.trim()) {
      setError("Paste an email or drop an .eml file first.")
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const res = file && override === undefined ? await api.createAnalysisFromFile(file) : await api.createAnalysisFromText(text)
      router.push(`/cases/${encodeURIComponent(res.id)}`)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong submitting the email."
      setError(msg)
      toast.error(msg)
      setSubmitting(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
      <BorderBeam className="min-w-0 rounded-[1.25rem]" radius={20} duration={8}>
        <form
          className="hud hud-glow flex h-full flex-col gap-4 p-5 sm:p-6"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <label htmlFor="raw" className="label-mono text-ink/80">
              Suspicious email
            </label>
            <span className="text-xs text-faint">Headers help: paste the full source if you can.</span>
          </div>

          {file ? (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-lime/30 bg-lime/5 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-mono text-sm text-ink">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB, ready to analyze</p>
              </div>
              <button
                type="button"
                onClick={() => setFile(null)}
                aria-label="Remove file"
                className="inline-flex size-8 items-center justify-center rounded-md border border-hair text-muted-foreground hover:text-ink"
              >
                <X className="size-4" />
              </button>
            </div>
          ) : (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                pickFile(e.dataTransfer.files?.[0])
              }}
              className={cn("relative flex flex-1 flex-col rounded-xl transition-colors", dragging && "ring-2 ring-lime")}
            >
              <textarea
                id="raw"
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                placeholder={"From: PayPal Security <security@paypa1-secure.com>\nSubject: Your account will be limited\n\nDear Customer, ..."}
                spellCheck={false}
                className="thin-scroll min-h-72 w-full flex-1 resize-y rounded-xl border border-hair bg-black/40 p-4 font-mono text-[13px] leading-relaxed text-ink placeholder:text-faint focus:border-lime/50 focus:outline-none sm:min-h-80"
              />
              {dragging ? (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl bg-black/70 font-mono text-sm text-lime">
                  Drop the .eml file
                </div>
              ) : null}
            </div>
          )}

          <input
            ref={inputRef}
            type="file"
            accept=".eml,.txt,message/rfc822,text/plain"
            className="sr-only"
            onChange={(e) => pickFile(e.target.files?.[0])}
          />

          {error ? (
            <p role="alert" className="rounded-lg border border-scam/30 bg-scam/5 px-3 py-2 text-sm text-scam">
              {error}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-11 items-center gap-2 rounded-full bg-lime px-6 text-sm font-semibold text-black transition-transform active:scale-[0.98] disabled:opacity-60"
            >
              {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
              {submitting ? "Starting analysis" : "Analyze"}
              {!submitting ? <ArrowRight className="size-4" /> : null}
            </button>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex h-11 items-center gap-2 rounded-full border border-hair px-5 text-sm text-ink transition-colors hover:border-lime/40"
            >
              <FileUp className="size-4 text-lime" /> Upload .eml
            </button>
            <span className="text-xs text-faint">Max 2 MB. Nothing is sent anywhere except the AEGIS analysis service.</span>
          </div>
        </form>
      </BorderBeam>

      <aside className="hud flex flex-col gap-3 p-5 sm:p-6" aria-labelledby="samples-title">
        <h2 id="samples-title" className="label-mono text-ink/80">
          Try a sample
        </h2>
        <p className="text-sm text-muted-foreground">Real-world patterns, ready to run. One click starts a live analysis.</p>
        {samplesFailed ? (
          <p className="text-sm text-faint">Samples are unavailable right now.</p>
        ) : !samples ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-white/[0.04]" />
            ))}
          </div>
        ) : samples.length === 0 ? (
          <p className="text-sm text-faint">No samples configured.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {samples.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    setFile(null)
                    setRaw(s.raw)
                    void submit(s.raw)
                  }}
                  className="group flex w-full items-start gap-3 rounded-xl border border-hair bg-black/30 p-3 text-left transition-colors hover:border-lime/40 disabled:opacity-60"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-ink">{s.title}</p>
                    <p className="line-clamp-2 text-xs text-muted-foreground">{s.description}</p>
                  </div>
                  <VerdictBadge label={s.expected} className="mt-0.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-auto pt-2 text-xs text-faint">The badge shows the expected verdict, so you can check AEGIS against it.</p>
      </aside>
    </div>
  )
}
