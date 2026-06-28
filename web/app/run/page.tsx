import { loadFunnel, loadRanked } from "@/lib/artifacts";
import { RankingCinema } from "@/components/cinema/RankingCinema";

/**
 * /run — Ranking Cinema. Server component loads the frozen funnel + top-10 from
 * the artifacts and hands them to the client cinema (WebGL lazy-loaded there).
 */
export default function RunPage() {
  const funnel = loadFunnel();
  const ranked = loadRanked();
  const top10 = [...ranked.candidates]
    .sort((a, b) => a.rank - b.rank)
    .slice(0, 10);
  return <RankingCinema funnel={funnel} top10={top10} />;
}
