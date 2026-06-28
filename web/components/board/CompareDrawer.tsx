"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RankedCandidate } from "@/lib/contracts";
import {
  fitComponents,
  availabilityScore,
  reachabilityScore,
  isProduct,
} from "@/lib/derive";
import { cn } from "@/lib/utils";

/**
 * Side-by-side compare (2–4 candidates). Requirement matrix (✓/~/✗), component
 * bars, and an "ATLAS's call" synthesis. The matrix + call are fully
 * deterministic (offline-safe); when a live backend is present the synthesis is
 * sharpened via /api/compare. Opens from its button or the ?compare URL param.
 */

type Req = { key: string; label: string; test: (c: RankedCandidate) => 0 | 1 | 2 };

const REQS: Req[] = [
  {
    key: "ranking",
    label: "Ranking / search / reco shipped",
    test: (c) =>
      /rank|search|recommend|reco|retrieval|l2r|ltr/i.test(c.reasoning) ? 2 : 0,
  },
  {
    key: "embeddings",
    label: "Production embeddings / retrieval",
    test: (c) =>
      /embedding|vector|faiss|rag|retrieval|index/i.test(c.reasoning) ? 2 : 1,
  },
  {
    key: "eval",
    label: "Ranking eval (NDCG/MRR/MAP, A/B)",
    test: (c) => (/ndcg|mrr|map|a\/b|eval/i.test(c.reasoning) ? 2 : 1),
  },
  {
    key: "product",
    label: "Product-company experience",
    test: (c) => (isProduct(c) ? 2 : 0),
  },
  {
    key: "yoe",
    label: "5–9 yrs (ideal 6–8)",
    test: (c) => (c.yoe >= 6 && c.yoe <= 8 ? 2 : c.yoe >= 5 && c.yoe <= 9 ? 1 : 0),
  },
  {
    key: "avail",
    label: "Available & reachable",
    test: (c) =>
      availabilityScore(c) >= 0.6 && reachabilityScore(c) >= 0.6
        ? 2
        : availabilityScore(c) >= 0.45
        ? 1
        : 0,
  },
];

const MARK = ["✗", "~", "✓"] as const;
const MARK_CLS = ["text-trap", "text-gold", "text-cyan"] as const;

export function CompareDrawer({
  candidates,
  live,
  openSignal,
  onConsumeSignal,
}: {
  candidates: RankedCandidate[];
  live: boolean;
  openSignal?: boolean;
  onConsumeSignal?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<number[]>([1, 2]);
  const [synthesis, setSynthesis] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (openSignal) {
      setOpen(true);
      onConsumeSignal?.();
    }
  }, [openSignal, onConsumeSignal]);

  const cols = useMemo(
    () =>
      picked
        .map((r) => candidates.find((c) => c.rank === r))
        .filter((c): c is RankedCandidate => !!c),
    [picked, candidates]
  );

  const leader = useMemo(
    () => (cols.length ? [...cols].sort((a, b) => a.rank - b.rank)[0] : null),
    [cols]
  );

  const localCall = leader
    ? `ATLAS's call: #${leader.rank} ${titleCase(leader.title)} @ ${
        leader.company
      } leads on graded fit${
        availabilityScore(leader) >= 0.6 ? " with strong availability" : ""
      }.`
    : "";

  function toggle(rank: number) {
    setSynthesis("");
    setPicked((prev) => {
      if (prev.includes(rank)) return prev.filter((r) => r !== rank);
      if (prev.length >= 4) return [...prev.slice(1), rank];
      return [...prev, rank];
    });
  }

  async function synthesize() {
    if (cols.length < 2) return;
    setLoading(true);
    try {
      const res = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ranks: cols.map((c) => c.rank) }),
      });
      const json = (await res.json()) as { synthesis?: string };
      setSynthesis(json.synthesis || localCall);
    } catch {
      setSynthesis(localCall);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg border border-glass-border bg-glass-fill px-4 py-2 text-sm text-ink-mute transition hover:text-ink"
      >
        Compare candidates
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
              aria-label="Compare candidates"
              aria-modal="true"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              className="glass fixed left-1/2 top-1/2 z-50 max-h-[88vh] w-[min(92vw,52rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl p-6 shadow-glass"
            >
              <div className="mb-4 flex items-start justify-between">
                <h2 className="text-lg font-semibold text-ink">
                  Compare candidates
                </h2>
                <button
                  onClick={() => setOpen(false)}
                  aria-label="Close"
                  className="rounded-lg border border-glass-border px-2 py-1 text-ink-mute hover:text-ink"
                >
                  ✕
                </button>
              </div>

              {/* Picker */}
              <div className="mb-4 flex flex-wrap gap-1.5">
                {candidates.slice(0, 20).map((c) => (
                  <button
                    key={c.candidate_id}
                    onClick={() => toggle(c.rank)}
                    className={cn(
                      "rounded-md border px-2 py-1 font-mono text-xs transition",
                      picked.includes(c.rank)
                        ? "border-gold/50 bg-gold/15 text-gold"
                        : "border-glass-border bg-glass-fill text-ink-mute hover:text-ink"
                    )}
                  >
                    #{c.rank}
                  </button>
                ))}
              </div>

              {cols.length < 2 ? (
                <p className="text-sm text-ink-mute">
                  Pick at least two candidates to compare.
                </p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr>
                          <th className="p-2 text-left text-ink-faint" />
                          {cols.map((c) => (
                            <th
                              key={c.candidate_id}
                              className="p-2 text-left align-bottom"
                            >
                              <div className="font-mono text-gold">#{c.rank}</div>
                              <div className="max-w-[10rem] truncate text-xs capitalize text-ink">
                                {c.title}
                              </div>
                              <div className="truncate text-[11px] text-ink-mute">
                                {c.company}
                              </div>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {REQS.map((req) => (
                          <tr key={req.key} className="border-t border-glass-border">
                            <td className="p-2 text-xs text-ink-mute">
                              {req.label}
                            </td>
                            {cols.map((c) => {
                              const v = req.test(c);
                              return (
                                <td
                                  key={c.candidate_id}
                                  className={cn(
                                    "p-2 text-center font-mono",
                                    MARK_CLS[v]
                                  )}
                                >
                                  {MARK[v]}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                        {/* component bars */}
                        {(["evidence", "behavioral"] as const).map((key) => (
                          <tr key={key} className="border-t border-glass-border">
                            <td className="p-2 text-xs capitalize text-ink-mute">
                              {key}
                            </td>
                            {cols.map((c) => {
                              const v =
                                fitComponents(c).find((x) => x.key === key)
                                  ?.value ?? 0;
                              return (
                                <td key={c.candidate_id} className="p-2">
                                  <span className="block h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                                    <span
                                      className="block h-full rounded-full bg-cyan"
                                      style={{ width: `${v * 100}%` }}
                                    />
                                  </span>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="mt-5 rounded-xl border border-gold/30 bg-gold/5 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-medium text-gold">
                        ATLAS&apos;s call
                      </h3>
                      <button
                        onClick={synthesize}
                        disabled={loading}
                        className="rounded-md border border-glass-border px-2.5 py-1 text-[11px] text-ink-mute hover:text-ink disabled:opacity-50"
                      >
                        {loading
                          ? "Synthesizing…"
                          : live
                          ? "Synthesize (live)"
                          : "Synthesize"}
                      </button>
                    </div>
                    <p className="mt-1.5 text-sm text-ink">
                      {synthesis || localCall}
                    </p>
                  </div>
                </>
              )}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (m) => m.toUpperCase());
}
