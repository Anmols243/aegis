// Gives each browser its viewer cookie on the first page load, before any
// API call fires, so every request from that browser carries the same viewer.
// Runs only on page routes that do not have the cookie yet.
import { NextResponse, type NextRequest } from "next/server"

import { VIEWER_COOKIE, VIEWER_MAX_AGE, isViewerToken, newViewerToken } from "@/lib/viewer"

export function proxy(request: NextRequest) {
  const response = NextResponse.next()
  if (!isViewerToken(request.cookies.get(VIEWER_COOKIE)?.value)) {
    const proto = request.headers.get("x-forwarded-proto") || request.nextUrl.protocol.replace(":", "")
    response.cookies.set(VIEWER_COOKIE, newViewerToken(), {
      path: "/",
      httpOnly: true,
      sameSite: "lax",
      secure: proto === "https",
      maxAge: VIEWER_MAX_AGE,
    })
  }
  return response
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|svg|jpg|ico|webp)$).*)",
      // must be a literal: matcher config is analysed at build time
      missing: [{ type: "cookie", key: "aegis_viewer" }],
    },
  ],
}
