// Same-origin proxy: the browser calls /api/*, this handler forwards to the
// AEGIS backend and attaches the API key server-side. The key never reaches
// the client bundle. Response bodies are streamed through untouched, so SSE
// (text/event-stream) arrives event by event.

import { newViewerToken, readViewerFromCookieHeader, viewerSetCookie } from "@/lib/viewer"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "")

// Hop-by-hop and length headers must not be copied between connections.
// The browser's cookies never reach the backend, and a client-sent viewer
// header is ignored: the viewer identity comes only from our HttpOnly cookie.
const DROP_REQUEST = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "authorization",
  "cookie",
  "keep-alive",
  "upgrade",
  "x-aegis-viewer",
])
const DROP_RESPONSE = new Set(["connection", "content-length", "transfer-encoding", "keep-alive", "content-encoding", "set-cookie"])

function clientIp(req: Request): string {
  const xff = req.headers.get("x-forwarded-for")
  if (xff) return xff
  const real = req.headers.get("x-real-ip")
  if (real) return real
  // No proxy in front of Next (local dev): the caller is this machine.
  return "127.0.0.1"
}

async function forward(req: Request, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params
  const incoming = new URL(req.url)
  const target = `${BACKEND_URL}/api/${path.map(encodeURIComponent).join("/")}${incoming.search}`

  const headers = new Headers()
  req.headers.forEach((value, key) => {
    if (!DROP_REQUEST.has(key.toLowerCase())) headers.set(key, value)
  })
  headers.set("x-forwarded-for", clientIp(req))
  const key = process.env.AEGIS_API_KEY
  if (key) headers.set("authorization", `Bearer ${key}`)

  // proxy.ts sets the cookie on the first page load; this is the fallback for
  // direct API use (and a cookie a page script somehow mangled).
  const existingViewer = readViewerFromCookieHeader(req.headers.get("cookie"))
  const viewer = existingViewer ?? newViewerToken()
  headers.set("x-aegis-viewer", viewer)

  const hasBody = req.method !== "GET" && req.method !== "HEAD"
  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      signal: req.signal,
      cache: "no-store",
      redirect: "manual",
    })
  } catch {
    return Response.json({ detail: "The AEGIS backend is unreachable." }, { status: 502 })
  }

  const out = new Headers()
  upstream.headers.forEach((value, key) => {
    if (!DROP_RESPONSE.has(key.toLowerCase())) out.set(key, value)
  })
  if ((upstream.headers.get("content-type") || "").includes("text/event-stream")) {
    out.set("cache-control", "no-cache, no-transform")
    out.set("x-accel-buffering", "no")
  }
  if (!existingViewer) {
    const proto = req.headers.get("x-forwarded-proto") || incoming.protocol.replace(":", "")
    out.append("set-cookie", viewerSetCookie(viewer, proto === "https"))
  }
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out })
}

export const GET = forward
export const POST = forward
export const PUT = forward
export const PATCH = forward
export const DELETE = forward
