import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { loadRanked, loadFunnel } from "@/lib/artifacts";
import { ShareBoard } from "@/components/share/ShareBoard";

/**
 * /share/[id] — read-only cinematic share card for a single top-100 candidate.
 * Carries an auto OG image (/api/og?id=...), a top-10 strip, the candidate's
 * verbatim reasoning, CSV + one-page PDF export, and a "Make your own ranking →"
 * CTA. Statically generated for all 100 ids.
 */

export function generateStaticParams() {
  const ranked = loadRanked();
  return ranked.candidates.map((c) => ({ id: c.candidate_id }));
}

export function generateMetadata({
  params,
}: {
  params: { id: string };
}): Metadata {
  let title = "ATLAS — shared ranking";
  try {
    const ranked = loadRanked();
    const c = ranked.candidates.find((x) => x.candidate_id === params.id);
    if (c)
      title = `#${c.rank} ${c.title} @ ${c.company} — ranked by ATLAS`;
  } catch {
    /* default */
  }
  const og = `/api/og?id=${encodeURIComponent(params.id)}`;
  return {
    title,
    openGraph: { title, images: [{ url: og, width: 1200, height: 630 }] },
    twitter: { card: "summary_large_image", title, images: [og] },
  };
}

export default function SharePage({ params }: { params: { id: string } }) {
  const ranked = loadRanked();
  const funnel = loadFunnel();
  const c = ranked.candidates.find((x) => x.candidate_id === params.id);
  if (!c) notFound();
  const top10 = [...ranked.candidates]
    .sort((a, b) => a.rank - b.rank)
    .slice(0, 10);
  const pool =
    funnel.stages.find((s) => s.name === "Candidate pool")?.count ?? 100000;
  return (
    <ShareBoard
      candidate={c}
      top10={top10}
      all={ranked.candidates}
      jobTitle={ranked.job_title}
      pool={pool}
      removed={funnel.honeypot_burn.total}
    />
  );
}
