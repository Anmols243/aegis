import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono, Montserrat } from "next/font/google"

import { AppBackground } from "@/components/aegis/app-background"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import "./globals.css"

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" })
const montserrat = Montserrat({ variable: "--font-montserrat", subsets: ["latin"], weight: ["600", "700", "800"], display: "swap" })
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" })

export const metadata: Metadata = {
  title: { default: "AEGIS: scam defense with evidence", template: "%s | AEGIS" },
  description:
    "Forward or paste a suspicious email. A team of AI agents dissects it and returns an evidence-cited verdict: SCAM, SUSPICIOUS, or LIKELY SAFE.",
}

export const viewport: Viewport = {
  themeColor: "#0a0c0e",
  colorScheme: "dark",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${montserrat.variable} ${jetbrains.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <AppBackground />
        <TooltipProvider delayDuration={150}>{children}</TooltipProvider>
        <Toaster theme="dark" position="bottom-center" />
      </body>
    </html>
  )
}
