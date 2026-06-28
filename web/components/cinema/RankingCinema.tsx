"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { Funnel, RankedCandidate } from "@/lib/contracts";
import { SankeyFallback } from "./SankeyFallback";

/**
 * Ranking Cinema orchestrator. ~15s, 4 acts over the WebGL particle funnel.
 * WebGL is lazy-loaded (only here, never on /board) and GPU-tiered: detect-gpu
 * picks a point budget (5K–20K). prefers-reduced-motion OR no-WebGL → the
 * animated Sankey of the same numbers. Act IV crystallizes into the top-10 grid
 * with a shared-element (layoutId) handoff to the Board.
 */

const ParticleFunnel = dynamic(() => import("./ParticleFunnel"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-ink-faint">
      Loading particle field…
    </div>
  ),
});

const ACTS = [
  {
    title: "The pool",
    caption: "100,000 candidates. Every dot is a real profile.",
  },
  {
    title: "Ignite the shortlist",
    caption:
      "BM25 + dense + rule recall scan → ~1,198 survive the first pass.",
  },
  {
    title: "Trap burn",
    caption: "Structural-impossibility honeypots combust and fall away.",
  },
  {
    title: "Crystallize",
    caption: "Top 100 → top 10. Ranked offline, CPU-only, in 73 seconds.",
  },
] as const;

const ACT_MS = 3800;

export function RankingCinema({
  funnel,
  top10,
}: {
  funnel: Funnel;
  top10: RankedCandidate[];
}) {
  const reduce = useReducedMotion();
  const [webglOk, setWebglOk] = useState<boolean | null>(null);
  const [count, setCount] = useState(8000);
  const [act, setAct] = useState(0);
  const [done, setDone] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // GPU tiering + WebGL capability probe (client only).
  useEffect(() => {
    let cancelled = false;
    async function probe() {
      // Capability check.
      try {
        const c = document.createElement("canvas");
        const gl =
          c.getContext("webgl2") || c.getContext("webgl");
        if (!gl) {
          if (!cancelled) setWebglOk(false);
          return;
        }
      } catch {
        if (!cancelled) setWebglOk(false);
        return;
      }
      // GPU tier → point budget.
      try {
        const { getGPUTier } = await import("detect-gpu");
        const tier = await getGPUTier();
        if (!cancelled) {
          const budget =
            tier.tier >= 3 ? 20000 : tier.tier === 2 ? 12000 : 6000;
          setCount(budget);
          setWebglOk(true);
        }
      } catch {
        if (!cancelled) {
          setCount(6000);
          setWebglOk(true);
        }
      }
    }
    if (reduce) {
      setWebglOk(false);
      return;
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [reduce]);

  // Drive the acts once we know we're rendering WebGL.
  useEffect(() => {
    if (webglOk !== true) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    for (let i = 1; i < ACTS.length; i++) {
      timers.current.push(setTimeout(() => setAct(i), ACT_MS * i));
    }
    timers.current.push(
      setTimeout(() => setDone(true), ACT_MS * ACTS.length)
    );
    return () => timers.current.forEach(clearTimeout);
  }, [webglOk]);

  // Reduced-motion / no-WebGL path: the Sankey of the same numbers.
  if (webglOk === false) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <header className="mb-8 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan">
            Ranking cinema · reduced motion
          </p>
          <h1 className="mt-2 text-2xl font-bold text-ink sm:text-3xl">
            100,000 → 10, the same numbers
          </h1>
        </header>
        <SankeyFallback funnel={funnel} />
        <div className="mt-10 text-center">
          <Link
            href="/board"
            className="inline-flex items-center gap-2 rounded-xl bg-gold px-6 py-3 font-semibold text-navy-900 shadow-glow"
          >
            See the board <span aria-hidden>→</span>
          </Link>
        </div>
      </div>
    );
  }

  if (webglOk === null) {
    return (
      <div className="flex h-[70vh] items-center justify-center text-ink-faint">
        Preparing the ranking cinema…
      </div>
    );
  }

  const burned = funnel.honeypot_burn.total;
  const showTrapCounter = act >= 2;

  return (
    <div className="relative h-[calc(100vh-57px)] w-full overflow-hidden">
      {/* WebGL stage */}
      <div className="absolute inset-0">
        <ParticleFunnel funnel={funnel} act={act} count={count} />
      </div>

      {/* Act caption overlay */}
      <div className="pointer-events-none absolute inset-x-0 top-10 z-10 text-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={act}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.5 }}
          >
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan">
              Act {act + 1} / {ACTS.length}
            </p>
            <h2 className="mt-2 text-2xl font-bold text-ink sm:text-3xl">
              {ACTS[act].title}
            </h2>
            <p className="mx-auto mt-2 max-w-xl text-ink-mute">
              {ACTS[act].caption}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Trap-burn counter */}
      <AnimatePresence>
        {showTrapCounter && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="pointer-events-none absolute bottom-28 left-1/2 z-10 -translate-x-1/2 rounded-xl border border-trap/40 bg-trap/10 px-5 py-3 text-center"
          >
            <span className="font-mono text-lg font-bold text-trap">
              −{burned} traps removed
            </span>
            <span className="mt-1 block text-xs text-ink-mute">
              0 honeypots will reach your top 100
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Crystallized top-10 handoff */}
      <AnimatePresence>
        {done && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-navy-900/70 backdrop-blur-sm"
          >
            <p className="mb-4 font-mono text-xs uppercase tracking-[0.3em] text-gold">
              Your top 10
            </p>
            <div className="grid max-w-2xl grid-cols-2 gap-2 px-4 sm:grid-cols-5">
              {top10.map((c) => (
                <motion.div
                  key={c.candidate_id}
                  layoutId={`cand-${c.candidate_id}`}
                  className="rounded-lg border border-gold/30 bg-navy-800/80 p-2 text-center"
                >
                  <div className="font-mono text-lg font-bold text-gold">
                    {c.rank}
                  </div>
                  <div className="truncate text-[11px] text-ink-mute">
                    {c.company}
                  </div>
                </motion.div>
              ))}
            </div>
            <Link
              href="/board"
              className="mt-8 inline-flex items-center gap-2 rounded-xl bg-gold px-6 py-3 font-semibold text-navy-900 shadow-glow transition hover:brightness-110"
            >
              Open the board <span aria-hidden>→</span>
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Skip control */}
      {!done && (
        <button
          onClick={() => {
            timers.current.forEach(clearTimeout);
            setAct(3);
            setDone(true);
          }}
          className="absolute bottom-5 right-5 z-30 rounded-full border border-glass-border bg-glass-fill px-4 py-2 text-sm text-ink-mute hover:text-ink"
        >
          Skip →
        </button>
      )}
    </div>
  );
}
