"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { RankedCandidate } from "@/lib/contracts";
import { fitComponents } from "@/lib/derive";
import { FitRing } from "@/components/viz/FitRing";

/**
 * Read-only cinematic share card. Renders the featured candidate, the top-10
 * strip, and export controls: the EXACT submission CSV (rebuilt from the frozen
 * artifact in candidate_id-ascending tie order) and a one-page top-10 PDF via
 * the browser's print pipeline (no extra dependency, deterministic output).
 */
export function ShareBoard({
  candidate,
  top10,
  all,
  jobTitle,
  pool,
  removed,
}: {
  candidate: RankedCandidate;
  top10: RankedCandidate[];
  all: RankedCandidate[];
  jobTitle: string;
  pool: number;
  removed: number;
}) {
  const comps = fitComponents(candidate);

  function exportCsv() {
    // Reproduce the submission contract: header + non-increasing score, ties
    // broken by candidate_id ascending (validator lines 136–144).
    const rows = [...all].sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.candidate_id.localeCompare(b.candidate_id);
    });
    const esc = (s: string) => `"${String(s).replace(/"/g, '""')}"`;
    const lines = ["candidate_id,rank,score,reasoning"];
    rows.forEach((c) => {
      lines.push(
        `${c.candidate_id},${c.rank},${c.score},${esc(c.reasoning)}`
      );
    });
    download("submission.csv", lines.join("\n"), "text/csv");
  }

  function exportPdf() {
    // The print-styled section (#print-sheet) is the one-page top-10; the
    // browser's "Save as PDF" produces the deliverable. Reliable + dependency
    // free; honors the ATLAS palette via print CSS in globals.
    window.print();
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan">
          Shared ranking · read-only
        </p>
        <div className="flex gap-2">
          <button
            onClick={exportCsv}
            className="rounded-lg border border-glass-border bg-glass-fill px-3 py-2 text-sm text-ink-mute hover:text-ink"
          >
            Export submission CSV
          </button>
          <button
            onClick={exportPdf}
            className="rounded-lg border border-glass-border bg-glass-fill px-3 py-2 text-sm text-ink-mute hover:text-ink"
          >
            Top-10 PDF
          </button>
        </div>
      </div>

      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass mb-8 grid gap-6 rounded-2xl p-6 shadow-glass md:grid-cols-[auto_1fr]"
      >
        <div className="flex flex-col items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-gold/40 bg-gold/10 font-mono text-lg font-bold text-gold">
            {candidate.rank}
          </span>
          <FitRing
            components={comps}
            size={132}
            stroke={11}
            centerLabel={Math.round(candidate.score * 100).toString()}
          />
        </div>
        <div>
          <h1 className="text-2xl font-bold capitalize text-ink">
            {candidate.title}
          </h1>
          <p className="mt-1 text-ink-mute">
            {candidate.company} · {candidate.yoe.toFixed(1)} yrs ·{" "}
            <span className="font-mono text-xs">{candidate.candidate_id}</span>
          </p>
          <p className="mt-4 text-sm leading-relaxed text-ink">
            {candidate.reasoning}
          </p>
          <p className="mt-4 text-xs text-ink-faint">
            Ranked #{candidate.rank} of {pool.toLocaleString()} screened ·{" "}
            {removed} traps removed · offline, CPU-only.
          </p>
        </div>
      </motion.section>

      {/* Print sheet — one-page top-10 */}
      <section id="print-sheet" className="glass rounded-2xl p-6 shadow-glass">
        <h2 className="mb-4 text-lg font-semibold text-ink">
          {jobTitle} — ATLAS top 10
        </h2>
        <ol className="space-y-2">
          {top10.map((c) => (
            <li
              key={c.candidate_id}
              className="flex items-center gap-3 border-b border-glass-border pb-2 text-sm"
            >
              <span className="w-6 font-mono font-bold text-gold">{c.rank}</span>
              <span className="flex-1 capitalize text-ink">
                {c.title} <span className="text-ink-mute">@ {c.company}</span>
              </span>
              <span className="font-mono text-xs text-ink-mute">
                {c.yoe.toFixed(1)}y
              </span>
            </li>
          ))}
        </ol>
      </section>

      <div className="mt-8 text-center print:hidden">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-xl bg-gold px-6 py-3 font-semibold text-navy-900 shadow-glow transition hover:brightness-110"
        >
          Make your own ranking <span aria-hidden>→</span>
        </Link>
      </div>
    </div>
  );
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
