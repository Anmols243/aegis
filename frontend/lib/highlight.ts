import type { Severity } from "@/lib/api"

export interface HighlightNote {
  claim: string
  severity: Severity
  source: string
}

export interface Segment {
  text: string
  notes: HighlightNote[]
}

const SEV_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2, info: 3 }

/**
 * Normalize for matching: lowercase and collapse whitespace runs to one space.
 * Returns the normalized string plus, for each normalized char, the index of
 * the original char it came from, so matches map back to the original text.
 */
function normalizeWithMap(src: string): { norm: string; map: number[] } {
  let norm = ""
  const map: number[] = []
  let inSpace = false
  for (let i = 0; i < src.length; i++) {
    const ch = src[i]
    if (/\s/.test(ch)) {
      if (!inSpace && norm.length > 0) {
        norm += " "
        map.push(i)
      }
      inSpace = true
    } else {
      norm += ch.toLowerCase()
      map.push(i)
      inSpace = false
    }
  }
  return { norm, map }
}

function normalize(s: string): string {
  return s.toLowerCase().replace(/\s+/g, " ").trim()
}

/**
 * Split `text` into segments, marking every occurrence of every excerpt.
 * Overlapping highlights are merged into one segment that carries all notes.
 */
export function highlightSegments(text: string, items: { excerpt: string; note: HighlightNote }[]): Segment[] {
  if (!text) return []
  const { norm, map } = normalizeWithMap(text)
  // Per original-char list of notes (sparse), built from every match range.
  const marks: (HighlightNote[] | undefined)[] = new Array(text.length)
  for (const { excerpt, note } of items) {
    const needle = normalize(excerpt || "")
    if (needle.length < 3) continue
    let from = 0
    for (;;) {
      const at = norm.indexOf(needle, from)
      if (at === -1) break
      const start = map[at]
      const end = map[at + needle.length - 1] + 1
      for (let i = start; i < end; i++) {
        const list = marks[i] ?? (marks[i] = [])
        if (!list.includes(note)) list.push(note)
      }
      from = at + needle.length
    }
  }
  const out: Segment[] = []
  let cur: Segment | null = null
  const key = (n: HighlightNote[] | undefined) => (n ? n.map((x) => `${x.source}:${x.claim}`).join("|") : "")
  let curKey = ""
  for (let i = 0; i < text.length; i++) {
    const n = marks[i]
    const k = key(n)
    if (!cur || k !== curKey) {
      cur = { text: "", notes: n ? [...n].sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity]) : [] }
      curKey = k
      out.push(cur)
    }
    cur.text += text[i]
  }
  return out
}

export function topSeverity(notes: HighlightNote[]): Severity {
  return notes.reduce<Severity>((best, n) => (SEV_RANK[n.severity] < SEV_RANK[best] ? n.severity : best), "info")
}
