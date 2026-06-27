import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { CoPilotDock } from "@/components/copilot/CoPilotDock";
import { StatusPill } from "@/components/StatusPill";
import { aiBackendLive } from "@/lib/utils";
import Link from "next/link";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"
  ),
  title: "ATLAS — Intelligent Candidate Discovery",
  description:
    "100,000 candidates screened, 201 traps removed, ranked in 73 seconds offline. Mission control for talent.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const live = aiBackendLive();
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-navy-700 focus:px-4 focus:py-2"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-40 border-b border-glass-border bg-navy-900/80 backdrop-blur">
          <nav
            className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3"
            aria-label="Primary"
          >
            <Link
              href="/"
              className="flex items-center gap-2 font-mono text-sm font-bold tracking-widest text-gold"
            >
              <span aria-hidden className="text-lg">
                ◎
              </span>
              ATLAS
            </Link>
            <div className="flex items-center gap-4 text-sm text-ink-mute">
              <Link href="/run" className="hover:text-ink">
                Cinema
              </Link>
              <Link href="/board" className="hover:text-ink">
                Board
              </Link>
              <Link href="/sandbox" className="hover:text-ink">
                Sandbox
              </Link>
              <StatusPill live={live} />
            </div>
          </nav>
        </header>
        <main id="main">{children}</main>
        <CoPilotDock live={live} />
      </body>
    </html>
  );
}
