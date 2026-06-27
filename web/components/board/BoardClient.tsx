"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, LayoutGroup } from "framer-motion";
import type { RankedCandidate } from "@/lib/contracts";
import { LENSES, type LensKey, applyLenses } from "@/lib/derive";
import { CandidateCard } from "./CandidateCard";
import { cn } from "@/lib/utils";

type Segment = 10 | 50 | 100;

/**
 * Board client: segmented Top10/Top50/All100 + left-rail lenses that re-order
 * client-side with FLIP (framer-motion `layout`) over precomputed components.
 * The lens is a VIEW — it never changes scores, only ordering — so it is fully
 * offline-safe and never re-ranks the model.
 */
export function BoardClient({ candidates }: { candidates: RankedCandidate[] }) {
  const [segment, setSegment] = useState<Segment>(10);
  const [active, setActive] = useState<LensKey[]>([]);

  const ordered = useMemo(() => {
    const sliced = candidates.slice(0, segment);
    return applyLenses(sliced, active);
  }, [candidates, segment, active]);

  function toggleLens(k: LensKey) {
    setActive((prev) =>
      prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]
    );
  }

  return (
    <div className="mx-auto max-w-7xl gap-6 px-4 lg:grid lg:grid-cols-[200px_1fr]">
      {/* Left rail — lenses */}
      <aside className="mb-6 lg:mb-0" aria-label="Lenses">
        <h2 className="mb-3 font-mono text-xs uppercase tracking-wider text-ink-mute">
          Lenses
        </h2>
        <div className="flex flex-wrap gap-2 lg:flex-col">
          {LENSES.map((l) => {
            const on = active.includes(l.key);
            return (
              <button
                key={l.key}
                onClick={() => toggleLens(l.key)}
                aria-pressed={on}
                className={cn(
                  "rounded-lg border px-3 py-2 text-left text-sm transition",
                  on
                    ? "border-cyan/50 bg-cyan/10 text-cyan"
                    : "border-glass-border bg-glass-fill text-ink-mute hover:text-ink"
                )}
              >
                <span aria-hidden className="mr-1.5">
                  {on ? "◉" : "○"}
                </span>
                {l.label}
              </button>
            );
          })}
        </div>
        {active.length > 0 && (
          <button
            onClick={() => setActive([])}
            className="mt-3 text-xs text-ink-faint underline hover:text-ink-mute"
          >
            Clear lenses
          </button>
        )}
        <p className="mt-4 text-xs text-ink-faint">
          Lenses re-order the view client-side. Scores never change.
        </p>
      </aside>

      <div>
        {/* Segmented control */}
        <div
          role="tablist"
          aria-label="Result size"
          className="mb-5 inline-flex rounded-xl border border-glass-border bg-glass-fill p-1"
        >
          {([10, 50, 100] as Segment[]).map((s) => (
            <button
              key={s}
              role="tab"
              aria-selected={segment === s}
              onClick={() => setSegment(s)}
              className={cn(
                "rounded-lg px-4 py-1.5 text-sm transition",
                segment === s
                  ? "bg-gold text-navy-900"
                  : "text-ink-mute hover:text-ink"
              )}
            >
              Top {s}
            </button>
          ))}
        </div>

        <LayoutGroup>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <AnimatePresence mode="popLayout">
              {ordered.map((c) => (
                <CandidateCard key={c.candidate_id} c={c} />
              ))}
            </AnimatePresence>
          </div>
        </LayoutGroup>
      </div>
    </div>
  );
}
