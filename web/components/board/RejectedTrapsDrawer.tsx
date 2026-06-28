"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RejectedTraps } from "@/lib/contracts";

/**
 * Rejected-traps drawer — "honeypot as a feature". Lists each clean structural
 * signature with its count, the seductive-surface / fatal-flaw pairing, and the
 * real example candidate_ids that were caught; plus the explicit "salary
 * inversion is NOT a trap" note, the soft-demoted (non-gating) signatures, and
 * the baseline foil. Opens from its own button OR via the ?rejected URL param
 * (deep-linkable from the cinema / share card).
 */

const SEDUCTIVE: Record<string, string> = {
  too_many_experts: "A wall of 'expert' skills looks elite on a keyword scan.",
  career_sum_exceeds_yoe: "Long, stacked tenures imply a deep veteran.",
  expert_zero_duration: "Expert-tagged skills inflate the skill match.",
  tenure_exceeds_company_age: "A long single tenure reads as loyalty + depth.",
  career_span_exceeds_yoe: "An early start date implies seniority.",
};

export function RejectedTrapsDrawer({
  traps,
  openSignal,
  onConsumeSignal,
}: {
  traps: RejectedTraps;
  /** external open trigger (e.g. ?rejected URL param) */
  openSignal?: boolean;
  onConsumeSignal?: () => void;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (openSignal) {
      setOpen(true);
      onConsumeSignal?.();
    }
  }, [openSignal, onConsumeSignal]);

  const total = traps.signatures.reduce((n, s) => n + s.count, 0);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg border border-trap/40 bg-trap/10 px-4 py-2 text-sm text-trap transition hover:bg-trap/20"
      >
        View {total} rejected traps →
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/60"
              onClick={() => setOpen(false)}
              aria-hidden
            />
            <motion.aside
              role="dialog"
              aria-label="Rejected traps"
              aria-modal="true"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "tween", duration: 0.3 }}
              className="glass fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col overflow-y-auto p-6 shadow-glass"
            >
              <div className="mb-1 flex items-start justify-between">
                <h2 className="text-lg font-semibold text-trap">
                  {traps.headline}
                </h2>
                <button
                  onClick={() => setOpen(false)}
                  aria-label="Close"
                  className="rounded-lg border border-glass-border px-2 py-1 text-ink-mute hover:text-ink"
                >
                  ✕
                </button>
              </div>
              <p className="mb-4 text-xs text-ink-faint">
                Each row pairs the seductive surface with the fatal flaw. Every id
                is a real candidate the gate excluded.
              </p>

              <div className="space-y-3">
                {traps.signatures.map((s) => (
                  <div
                    key={s.signature}
                    className="rounded-xl border border-glass-border bg-glass-fill p-4"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm text-ink">
                        {s.signature}
                      </span>
                      <span className="rounded-full bg-trap/15 px-2 py-0.5 font-mono text-xs text-trap">
                        {s.count}
                      </span>
                    </div>
                    {SEDUCTIVE[s.signature] && (
                      <p className="mt-1.5 text-xs italic text-gold/80">
                        Surface: {SEDUCTIVE[s.signature]}
                      </p>
                    )}
                    <p className="mt-1 text-xs leading-relaxed text-ink-mute">
                      <span className="text-trap">Fatal flaw:</span> {s.why_fatal}
                    </p>
                    {s.examples?.length > 0 && (
                      <p className="mt-2 truncate font-mono text-[10px] text-ink-faint">
                        {s.examples.slice(0, 5).join(" · ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-5 rounded-xl border border-cyan/30 bg-cyan/5 p-4">
                <h3 className="text-sm font-medium text-cyan">
                  Deliberately NOT a trap
                </h3>
                <p className="mt-1 text-xs text-ink-mute">
                  <span className="font-mono">{traps.not_a_trap.signature}</span>{" "}
                  fires on {traps.not_a_trap.fires_on.toLocaleString()} candidates.{" "}
                  {traps.not_a_trap.note}
                </p>
              </div>

              {Object.keys(traps.soft_demoted ?? {}).length > 0 && (
                <div className="mt-3 rounded-xl border border-glass-border bg-glass-fill p-4">
                  <h3 className="text-sm font-medium text-ink">
                    Demoted to soft (never gates alone)
                  </h3>
                  <ul className="mt-1.5 space-y-1 text-xs text-ink-mute">
                    {Object.entries(traps.soft_demoted).map(([k, v]) => (
                      <li key={k} className="flex justify-between gap-2">
                        <span className="font-mono">{k}</span>
                        <span className="font-mono text-ink-faint">
                          {v.toLocaleString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[11px] text-ink-faint">
                    Too common to be planted traps — they contribute only a small
                    negative signal, never a hard exclude.
                  </p>
                </div>
              )}

              <div className="mt-3 rounded-xl border border-glass-border bg-glass-fill p-4">
                <h3 className="text-sm font-medium text-ink">Baseline foil</h3>
                <p className="mt-1 text-xs text-ink-mute">
                  {traps.baseline_foil.note}
                </p>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
