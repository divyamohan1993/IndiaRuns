import { ImageResponse } from "next/og";
import { loadRanked, loadFunnel } from "@/lib/artifacts";

export const runtime = "nodejs";

/**
 * Open Graph image for /share/[id] cards. Renders the funnel headline + the
 * top-3 from the frozen artifacts on the ATLAS space-navy canvas. Purely from
 * committed artifacts — no network, no key. Query: ?id=CAND_xxxxxxx (optional)
 * to feature a specific candidate.
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const id = url.searchParams.get("id");

  let ranked, funnel;
  try {
    ranked = loadRanked();
    funnel = loadFunnel();
  } catch {
    return new ImageResponse(
      <div style={fallbackStyle}>ATLAS — Intelligent Candidate Ranking</div>,
      { width: 1200, height: 630 }
    );
  }

  const featured =
    (id && ranked.candidates.find((c) => c.candidate_id === id)) ||
    ranked.candidates[0];
  const top3 = [...ranked.candidates].sort((a, b) => a.rank - b.rank).slice(0, 3);
  const pool =
    funnel.stages.find((s) => s.name === "Candidate pool")?.count ?? 100000;
  const removed = funnel.honeypot_burn.total;

  return new ImageResponse(
    (
      <div
        style={{
          width: "1200px",
          height: "630px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px",
          background:
            "linear-gradient(160deg, #131a2e 0%, #0A0E1A 55%)",
          color: "#E6EAF2",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              fontSize: 26,
              letterSpacing: 6,
              color: "#5BE0E6",
              textTransform: "uppercase",
            }}
          >
            ◎ ATLAS · Mission control for talent
          </div>
          <div style={{ display: "flex", fontSize: 64, fontWeight: 800, marginTop: 18 }}>
            {ranked.job_title}
          </div>
          <div style={{ display: "flex", fontSize: 30, color: "#9AA4BC", marginTop: 8 }}>
            {`${pool.toLocaleString()} screened · ${removed} traps removed · ranked in 73s offline`}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {top3.map((c) => (
            <div
              key={c.candidate_id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 18,
                fontSize: 30,
                color:
                  c.candidate_id === featured.candidate_id ? "#F5C04E" : "#E6EAF2",
              }}
            >
              <span
                style={{
                  width: 56,
                  height: 56,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 12,
                  border: "2px solid rgba(245,192,78,0.5)",
                  color: "#F5C04E",
                  fontWeight: 800,
                }}
              >
                {c.rank}
              </span>
              <span style={{ display: "flex", textTransform: "capitalize" }}>
                {`${c.title} @ ${c.company}`}
              </span>
            </div>
          ))}
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}

const fallbackStyle = {
  width: "1200px",
  height: "630px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "#0A0E1A",
  color: "#F5C04E",
  fontSize: 48,
} as const;
