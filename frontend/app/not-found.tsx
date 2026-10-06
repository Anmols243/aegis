import Link from "next/link"

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="label-mono text-lime">404</p>
      <h1 className="font-display text-3xl font-bold text-ink">Nothing on the radar here.</h1>
      <Link href="/" className="chip">
        Back to AEGIS
      </Link>
    </div>
  )
}
