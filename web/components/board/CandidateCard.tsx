"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { RankedCandidate } from "@/lib/contracts";
import {
  fitComponents,
  availabilityScore,
  reachabilityScore,
  trustPips,
  isProduct,
} from "@/lib/derive";
import { FitRing } from "@/components/viz/FitRing";
import { cn } from "@/lib/utils";

/**
 * Board candidate card. Rank badge, segmented fit ring, availability +
 * reachability gauges (compact bars), title@company with product-vs-services
 * chip, YOE, one-line evidence, trust pips. Uses layoutId for the shared-element
 * transition into the detail page.
 */
export function CandidateCard({ c }: { c: RankedCandidate }) {
  const comps = fitComponents(c);
  const avail = availabilityScore(c);
  const reach = reachabilityScore(c);
  const pips = trustPips(c);
  const product = isProduct(c);

  return (
    <motion.div layout layoutId={`card-${c.rank}`}>
      <Link
        href={`/board/${c.rank}`}
        className="glass group block rounded-2xl p-4 shadow-glass transition hover:border-gold/40 hover:shadow-glow focus-visible:border-cyan"
      >
        <div className="flex items-start gap-4">
          <div className="flex flex-col items-center gap-2">
            <span
              aria-label={`Rank ${c.rank}`}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-gold/40 bg-gold/10 font-mono text-sm font-bold text-gold"
            >
              {c.rank}
            </span>
            <FitRing
              components={comps}
              size={64}
              stroke={7}
              centerLabel={Math.round(c.score * 100).toString()}
            />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-sm font-semibold capitalize text-ink">
                {c.title}
              </h3>
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-mute">
              <span className="truncate">{c.company}</span>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
                  product
                    ? "border-cyan/40 bg-cyan/10 text-cyan"
                    : "border-trap/40 bg-trap/10 text-trap"
                )}
              >
                {product ? "Product" : "Services"}
              </span>
              <span className="shrink-0 font-mono">{c.yoe.toFixed(1)}y</span>
            </div>

            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-ink-mute">
              {c.reasoning}
            </p>

            <div className="mt-3 flex items-center gap-4">
              <MiniBar label="Avail" value={avail} color="#5BE0E6" />
              <MiniBar label="Reach" value={reach} color="#F5C04E" />
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {pips
                .filter((p) => p.on)
                .map((p) => (
                  <span
                    key={p.label}
                    className="rounded-full border border-glass-border bg-glass-fill px-1.5 py-0.5 text-[10px] text-ink-mute"
                  >
                    {p.label}
                  </span>
                ))}
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

function MiniBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="font-mono text-[10px] uppercase text-ink-faint">
        {label}
      </span>
      <span
        className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value * 100)}
        aria-label={`${label} ${Math.round(value * 100)} of 100`}
      >
        <span
          className="block h-full rounded-full"
          style={{ width: `${value * 100}%`, backgroundColor: color }}
        />
      </span>
    </div>
  );
}
