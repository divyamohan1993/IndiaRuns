"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { Funnel } from "@/lib/contracts";

/**
 * Reduced-motion / no-WebGL fallback for the Ranking Cinema. An animated Sankey
 * of the SAME numbers from funnel.json — pool → honeypots removed → shortlist →
 * top 100 → top 10. Pure SVG + framer-motion (respects prefers-reduced-motion,
 * in which case bars simply appear). No GPU, fully accessible.
 */
export function SankeyFallback({ funnel }: { funnel: Funnel }) {
  const reduce = useReducedMotion();
  const stages = funnel.stages;
  const max = Math.max(...stages.map((s) => s.count), 1);

  // Log scale so 100K → 10 stays legible.
  const widthFor = (n: number) =>
    8 + (Math.log10(n + 1) / Math.log10(max + 1)) * 92;

  const colorFor = (name: string) => {
    if (/honeypot|trap/i.test(name)) return "#FF5C6C";
    if (/top 10\b/i.test(name)) return "#F5C04E";
    if (/top 100/i.test(name)) return "#F5C04E";
    if (/shortlist/i.test(name)) return "#5BE0E6";
    return "#6E8BFF";
  };

  return (
    <div
      className="mx-auto max-w-3xl space-y-4"
      role="img"
      aria-label={
        "Funnel: " + stages.map((s) => `${s.name} ${s.count}`).join(", ")
      }
    >
      {stages.map((s, i) => (
        <div key={s.name} className="flex items-center gap-4">
          <div className="w-44 shrink-0 text-right text-sm text-ink-mute">
            {s.name}
          </div>
          <div className="relative h-8 flex-1 overflow-hidden rounded-md bg-glass-fill">
            <motion.div
              className="h-full rounded-md"
              style={{ backgroundColor: colorFor(s.name), opacity: 0.85 }}
              initial={{ width: reduce ? `${widthFor(s.count)}%` : 0 }}
              whileInView={{ width: `${widthFor(s.count)}%` }}
              viewport={{ once: true }}
              transition={{ duration: reduce ? 0 : 0.8, delay: i * 0.25 }}
            />
          </div>
          <div className="w-24 shrink-0 font-mono text-sm text-ink">
            {s.count.toLocaleString()}
          </div>
        </div>
      ))}
      <p className="pt-2 text-center text-xs text-ink-faint">
        −{funnel.honeypot_burn.total} traps removed · 0 honeypots reach your top
        100 · recall gate {funnel.recall_gate.gate_passed ? "PASS" : "—"} (Tier-5{" "}
        {Math.round(funnel.recall_gate.tier5.recall * 100)}%, Tier-4{" "}
        {Math.round(funnel.recall_gate.tier4.recall * 100)}%)
      </p>
    </div>
  );
}
