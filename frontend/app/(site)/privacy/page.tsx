import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = { title: "Privacy" }

// Every statement here must match a guarantee in docs/API.md or the backend
// configuration. Third parties are described only by what AEGIS sends them.
const SECTIONS: { title: string; body: React.ReactNode }[] = [
  {
    title: "The short version",
    body: (
      <ul className="flex list-disc flex-col gap-1.5 pl-5">
        <li>AEGIS has no accounts, no analytics and no ads.</li>
        <li>Emails you paste or upload are private by default: unlisted, never in the public feed or campaign graph.</li>
        <li>Emails sent to the test inbox are shown on the public Live page, partially censored.</li>
        <li>Email text is deleted after a retention period (7 days by default). The verdict is kept.</li>
        <li>To analyze an email, its content is sent to AI models hosted by Featherless.</li>
      </ul>
    ),
  },
  {
    title: "What is stored, and for how long",
    body: (
      <>
        <p>For each analysis AEGIS stores the email you submitted, the verdict, the evidence it cites, and how long each step took.</p>
        <ul className="mt-2 flex list-disc flex-col gap-1.5 pl-5">
          <li>
            <strong className="text-ink">Pasted and uploaded emails</strong> are private. After the retention period (7 days by default) the email
            text is deleted and only the verdict and its summary remain.
          </li>
          <li>
            <strong className="text-ink">Built-in samples and red-team variants</strong> are synthetic and public.
          </li>
          <li>
            <strong className="text-ink">Emails sent to the test inbox</strong> are listed on the public{" "}
            <Link href="/live" className="text-lime underline-offset-4 hover:underline">
              Live
            </Link>{" "}
            page with their subject, a preview and the full analysis. Names are cut to initials, addresses to their first two characters, and long
            numbers and codes are shortened; links and domains stay visible because they are the evidence. Do not send personal mail there.
          </li>
          <li>
            <strong className="text-ink">Campaign indicators</strong> (sender, domains, links, phone numbers, a template fingerprint) are kept so that
            related scams can be linked. Other people only ever see that &quot;a private email shares this infrastructure&quot;, never its subject, sender
            or content.
          </li>
        </ul>
      </>
    ),
  },
  {
    title: "What is sent to other services",
    body: (
      <ul className="flex list-disc flex-col gap-1.5 pl-5">
        <li>
          <strong className="text-ink">Featherless AI</strong> hosts the language and vision models. The email content (and, for HTML email, a
          screenshot of it rendered offline) is sent there for analysis. How Featherless handles requests is covered by{" "}
          <a href="https://featherless.ai" target="_blank" rel="noopener noreferrer" className="text-lime underline-offset-4 hover:underline">
            their policies
          </a>
          .
        </li>
        <li>
          <strong className="text-ink">AgentBoxD</strong> provides the AEGIS test inbox. Only mail you send to that address passes through it, and
          the verdict is replied to you through it. Pasted emails never go to AgentBoxD.
        </li>
        <li>
          <strong className="text-ink">Links in the email</strong> are fetched by the AEGIS link sandbox, without JavaScript and without cookies, so
          the sites they point to see a request from AEGIS, not from you.
        </li>
      </ul>
    ),
  },
  {
    title: "Cookies",
    body: (
      <p>
        AEGIS sets one cookie, <code className="font-mono text-ink">aegis_viewer</code>. It holds a random value that says which private results belong
        to this browser. It is HttpOnly (page scripts cannot read it), is not linked to your name or email, and is not used for
        analytics or tracking. Clearing it means this browser can no longer list your private results; anything you still have a link to stays
        reachable through that link until it is deleted.
      </p>
    ),
  },
  {
    title: "Links and sharing",
    body: (
      <p>
        Every case has a long random address. Anyone with that address can open it, so treat it like a password. The share link shows a reduced
        version for friends and family: the verdict, red flags and next steps, without the full email text.
      </p>
    ),
  },
  {
    title: "How to delete your data",
    body: (
      <ul className="flex list-disc flex-col gap-1.5 pl-5">
        <li>Email text is deleted automatically after the retention period.</li>
      </ul>
    ),
  },
]

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <p className="label-mono mb-2 text-lime">Privacy</p>
      <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Your email is yours</h1>
      <p className="mt-3 text-muted-foreground">
        A scam checker has to read email to do its job. This page says plainly what AEGIS keeps, what it shares, and how to make it forget.
      </p>
      <div className="mt-10 flex flex-col gap-4">
        {SECTIONS.map((s) => (
          <section key={s.title} className="hud p-5 sm:p-6">
            <h2 className="mb-3 font-display text-lg font-bold tracking-tight text-ink">{s.title}</h2>
            <div className="text-[14.5px] leading-relaxed text-muted-foreground">{s.body}</div>
          </section>
        ))}
      </div>
    </div>
  )
}
