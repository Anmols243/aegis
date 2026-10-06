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
        <li>Emails you analyze are private by default: unlisted, never in the public feed or campaign graph.</li>
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
            <strong className="text-ink">Pasted, uploaded and mailbox emails</strong> are private. After the retention period (7 days by default, or
            what you chose when connecting a mailbox) the email text is deleted and only the verdict and its summary remain.
          </li>
          <li>
            <strong className="text-ink">Built-in samples and red-team variants</strong> are synthetic and public.
          </li>
          <li>
            <strong className="text-ink">Connected mailboxes:</strong> the address, your chosen retention period, scan counts and the sign-in token from Google or
            Microsoft. The token is encrypted at rest with AES-256-GCM and is never sent back to the browser.
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
          screenshot of it rendered offline) is sent there for analysis. For a connected mailbox, your own address is replaced with
          &quot;[your address]&quot; first. How Featherless handles requests is covered by{" "}
          <a href="https://featherless.ai" target="_blank" rel="noopener noreferrer" className="text-lime underline-offset-4 hover:underline">
            their policies
          </a>
          .
        </li>
        <li>
          <strong className="text-ink">AgentBoxD</strong> provides the AEGIS forwarding inbox. Only mail you choose to forward to that inbox passes
          through it. Connected mailboxes and pasted emails never go to AgentBoxD.
        </li>
        <li>
          <strong className="text-ink">Links in the email</strong> are fetched by the AEGIS link sandbox, without JavaScript and without cookies, so
          the sites they point to see a request from AEGIS, not from you.
        </li>
      </ul>
    ),
  },
  {
    title: "Connected mailboxes",
    body: (
      <ul className="flex list-disc flex-col gap-1.5 pl-5">
        <li>Only mail that arrives after you connect is scanned. Existing mail is never read.</li>
        <li>Mail is read without being marked as read.</li>
        <li>AEGIS only adds a label (Gmail) or a category and flag (Outlook). It never moves, deletes, forwards or sends mail.</li>
        <li>You connect with Sign in with Google or Microsoft. AEGIS never sees your password, and you can remove its access at any time.</li>
        <li>Google: one permission, read mail and add labels (gmail.modify). Microsoft: read and update mail (Mail.ReadWrite, the narrowest scope that allows tagging). AEGIS never uses them to send, move or delete.</li>
      </ul>
    ),
  },
  {
    title: "Cookies",
    body: (
      <p>
        AEGIS sets one cookie, <code className="font-mono text-ink">aegis_viewer</code>. It holds a random value that says which private results and
        mailboxes belong to this browser. It is HttpOnly (page scripts cannot read it), is not linked to your name or email, and is not used for
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
        <li>
          On the{" "}
          <Link href="/inbox" className="text-lime underline-offset-4 hover:underline">
            Inbox
          </Link>{" "}
          page, disconnect a mailbox and tick &quot;also delete all analyses from this mailbox&quot;. The stored sign-in token is deleted immediately; for Google accounts, access is also revoked at Google.
        </li>
        <li>Email text is deleted automatically after the retention period.</li>
        <li>For Microsoft accounts, also remove AEGIS under your account&apos;s app permissions (Microsoft offers no way for an app to give its access back).</li>
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
