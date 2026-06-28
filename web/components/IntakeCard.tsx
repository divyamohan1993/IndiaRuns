"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { REDROB_JD } from "@/lib/jd";
import { IntentChip } from "./IntentChip";
import type { Intent } from "@/lib/contracts";

/**
 * JD intake card. Pre-filled with the Redrob JD; shows the frozen intent chip
 * cloud (must-haves gold, anti-patterns struck red, behavioral cyan). The CTA
 * routes to the ranking board. Live parse via the AI backend lands next stage;
 * the frozen intent.json is always the source of truth offline.
 */
export function IntakeCard({ intent }: { intent: Intent }) {
  const router = useRouter();
  const [jd, setJd] = useState(REDROB_JD);

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 lg:grid-cols-[1.1fr_0.9fr]">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="glass rounded-2xl p-6 shadow-glass"
      >
        <label
          htmlFor="jd"
          className="mb-2 block font-mono text-xs uppercase tracking-wider text-ink-mute"
        >
          Job description
        </label>
        <textarea
          id="jd"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          rows={16}
          className="w-full resize-y rounded-xl border border-glass-border bg-navy-900 p-4 text-sm leading-relaxed text-ink placeholder:text-ink-faint"
          aria-describedby="jd-help"
        />
        <p id="jd-help" className="mt-2 text-xs text-ink-faint">
          Pre-filled with the Redrob Senior AI Engineer JD. Decomposed into{" "}
          {intent.clause_count} weighted requirement clauses.
        </p>

        <button
          onClick={() => router.push("/run")}
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gold px-6 py-4 text-lg font-semibold text-navy-900 shadow-glow transition hover:brightness-110"
        >
          Run the ranking
          <span aria-hidden>→</span>
        </button>
        <button
          onClick={() => router.push("/board")}
          className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-glass-border px-6 py-2.5 text-sm text-ink-mute transition hover:text-ink"
        >
          Skip to the board
        </button>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="space-y-5"
      >
        <ChipGroup title="Must-haves" chips={intent.must_haves} />
        <ChipGroup title="Anti-patterns (excluded)" chips={intent.anti_patterns} />
        <ChipGroup title="Behavioral preferences" chips={intent.behavioral} />
      </motion.div>
    </div>
  );
}

function ChipGroup({ title, chips }: { title: string; chips: Intent["must_haves"] }) {
  return (
    <section aria-label={title}>
      <h2 className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-mute">
        {title}
      </h2>
      <div className="flex flex-wrap gap-2">
        {chips.map((c) => (
          <IntentChip key={c.label} chip={c} />
        ))}
      </div>
    </section>
  );
}
