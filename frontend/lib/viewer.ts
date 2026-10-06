// Viewer token: 32 random bytes, base64url (43 chars). It is the only cookie
// AEGIS sets. It is functional (it says which private analyses and mailboxes
// belong to this browser), HttpOnly so page scripts cannot read it, and not
// tied to any account, analytics or tracking. Server-side use only.

export const VIEWER_COOKIE = "aegis_viewer"
export const VIEWER_MAX_AGE = 60 * 60 * 24 * 365
const VIEWER_RE = /^[A-Za-z0-9_-]{43}$/

export function isViewerToken(value: string | null | undefined): value is string {
  return !!value && VIEWER_RE.test(value)
}

export function newViewerToken(): string {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  let bin = ""
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

export function readViewerFromCookieHeader(raw: string | null): string | null {
  if (!raw) return null
  for (const part of raw.split(";")) {
    const [name, ...rest] = part.trim().split("=")
    if (name === VIEWER_COOKIE) {
      const value = rest.join("=")
      return isViewerToken(value) ? value : null
    }
  }
  return null
}

export function viewerSetCookie(token: string, secure: boolean): string {
  return `${VIEWER_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${VIEWER_MAX_AGE}${secure ? "; Secure" : ""}`
}
