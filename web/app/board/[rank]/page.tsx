import { notFound } from "next/navigation";
import Link from "next/link";
import { loadRanked } from "@/lib/artifacts";
import {
  fitComponents,
  gauges,
  signals,
  skillChips,
  isProduct,
} from "@/lib/derive";
import { FitRing } from "@/components/viz/FitRing";
import { Gauge } from "@/components/viz/Gauge";
import { EvidenceBlock } from "@/components/board/EvidenceBlock";
import { SignalsPanel } from "@/components/board/SignalsPanel";
import { SkillChips } from "@/components/board/SkillChips";
import { OutreachButton } from "@/components/board/OutreachButton";
import { cn } from "@/lib/utils";

// Pre-render all 100 detail pages at build time.
export function generateStaticParams() {
  const ranked = loadRanked();
  return ranked.candidates.map((c) => ({ rank: String(c.rank) }));
}

export default function CandidateDetail({
  params,
}: {
  params: { rank: string };
}) {
  const rank = Number(params.rank);
  const ranked = loadRanked();
  const c = ranked.candidates.find((x) => x.rank === rank);
  if (!c) notFound();

  const comps = fitComponents(c);
  const gs = gauges(c);
  const sigs = signals(c);
  const skills = skillChips(c);
  const product = isProduct(c);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        href="/board"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-ink-mute hover:text-ink"
      >
        <span aria-hidden>←</span> Back to board
      </Link>

      {/* Zone A — identity + fit ring + verbatim reasoning */}
      <section className="glass mb-6 grid gap-6 rounded-2xl p-6 shadow-glass md:grid-cols-[auto_1fr]">
        <div className="flex flex-col items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-gold/40 bg-gold/10 font-mono text-lg font-bold text-gold">
            {c.rank}
          </span>
          <FitRing
            components={comps}
            size={148}
            stroke={12}
            centerLabel={Math.round(c.score * 100).toString()}
          />
          <ul className="space-y-1 text-xs">
            {comps.map((cp) => (
              <li key={cp.key} className="flex items-center gap-1.5">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: cp.color }}
                  aria-hidden
                />
                <span className="text-ink-mute">{cp.label}</span>
                <span className="ml-auto font-mono text-ink">
                  {Math.round(cp.value * 100)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold capitalize text-ink">
              {c.title}
            </h1>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-wide",
                product
                  ? "border-cyan/40 bg-cyan/10 text-cyan"
                  : "border-trap/40 bg-trap/10 text-trap"
              )}
            >
              {product ? "Product" : "Services"}
            </span>
          </div>
          <p className="mt-1 text-ink-mute">
            {c.company} · {c.yoe.toFixed(1)} yrs ·{" "}
            <span className="font-mono text-xs">{c.candidate_id}</span>
          </p>

          <div className="mt-5">
            <EvidenceBlock reasoning={c.reasoning} />
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <OutreachButton rank={c.rank} />
            <Link
              href={`/share/${c.candidate_id}`}
              className="rounded-lg border border-glass-border bg-glass-fill px-3 py-2 text-sm text-ink-mute transition hover:text-ink"
            >
              Share card →
            </Link>
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Zone B — skills */}
        <section className="glass rounded-2xl p-6 shadow-glass">
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-ink-mute">
            Skills (✓ verified · ⚠ unverified expert)
          </h2>
          <SkillChips chips={skills} />
        </section>

        {/* Zone C — gauges */}
        <section className="glass rounded-2xl p-6 shadow-glass">
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-ink-mute">
            Availability · Reachability · Demand-trust
          </h2>
          <div className="flex flex-wrap items-end justify-around gap-4">
            {gs.map((g) => (
              <Gauge key={g.key} label={g.label} value={g.value} color={g.color} />
            ))}
          </div>
        </section>
      </div>

      {/* The 23 signals */}
      <section className="glass mt-6 rounded-2xl p-6 shadow-glass">
        <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-ink-mute">
          Signals
        </h2>
        <SignalsPanel signals={sigs} />
      </section>
    </div>
  );
}
