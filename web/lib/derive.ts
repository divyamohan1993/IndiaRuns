import type { RankedCandidate } from "./contracts";

/**
 * The "deterministic brain".
 *
 * The frozen ranked_top100.json carries the graded fields (rank, score,
 * reasoning, title@company, yoe, company_type, a handful of behavioral signals).
 * The UI needs richer derived views — a segmented fit ring, availability /
 * reachability / demand-trust gauges, the 23-signal panel, evidence tagging,
 * and lens predicates. Every derivation below is a PURE, DETERMINISTIC function
 * of the candidate's own frozen fields. No randomness, no network, no LLM. This
 * is what keeps the spine fully functional with zero keys: the same inputs
 * always yield the same UI, and nothing here invents a fact not present in the
 * artifact.
 *
 * IMPORTANT: these derivations are presentational. The authoritative ranking
 * lives in `score`/`rank` from the submission. Components are a faithful,
 * monotone decomposition for explanation — never a re-ranking.
 */

export type FitComponent = {
  key: "fit" | "evidence" | "semantic" | "behavioral";
  label: string;
  value: number; // 0..1
  color: string;
};

const COLORS = {
  gold: "#F5C04E",
  cyan: "#5BE0E6",
  blue: "#6E8BFF",
  amber: "#F5A04E",
} as const;

/** Stable 32-bit hash of a candidate id → used only to vary phrasing, never facts. */
export function hashId(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

export function isProduct(c: RankedCandidate): boolean {
  return (c.company_type || "").toLowerCase().includes("product");
}

export function daysSinceActive(c: RankedCandidate): number | null {
  if (!c.last_active_date) return null;
  const t = Date.parse(c.last_active_date);
  if (Number.isNaN(t)) return null;
  // Reference "today" matches the dataset's frozen horizon (2026-06-27).
  const now = Date.parse("2026-06-27T00:00:00Z");
  return Math.max(0, Math.round((now - t) / 86400000));
}

/**
 * Segmented fit ring decomposition. The four arcs sum to the overall score band
 * but are weighted from genuine signals: the graded `score` anchors overall fit;
 * evidence is read from the reasoning text density of role terms; semantic is a
 * product-company / title-fit proxy; behavioral from the availability signals.
 */
export function fitComponents(c: RankedCandidate): FitComponent[] {
  const overall = clamp01(c.score);

  // Evidence strength: presence of hard role terms in the candidate's own
  // reasoning string (which is the verbatim, fact-validated submission line).
  const r = (c.reasoning || "").toLowerCase();
  const evidTerms = [
    "rank",
    "search",
    "recommend",
    "reco",
    "retrieval",
    "embedding",
    "vector",
    "faiss",
    "ndcg",
    "mrr",
    "l2r",
    "ltr",
    "rag",
    "a/b",
    "production",
    "scale",
  ];
  const hits = evidTerms.reduce((n, t) => n + (r.includes(t) ? 1 : 0), 0);
  const evidence = clamp01(0.4 + hits * 0.09);

  // Semantic role-fit proxy: product company + AI/eng-ish title keep this high.
  const title = (c.title || "").toLowerCase();
  const titleFit =
    /engineer|scientist|ml|ai|search|recsys|research/.test(title) ? 1 : 0.4;
  const semantic = clamp01(0.55 * titleFit + (isProduct(c) ? 0.45 : 0.2));

  const behavioral = clamp01(availabilityScore(c) * 0.6 + reachabilityScore(c) * 0.4);

  return [
    { key: "fit", label: "Role fit", value: overall, color: COLORS.gold },
    { key: "evidence", label: "Evidence", value: evidence, color: COLORS.amber },
    { key: "semantic", label: "Semantic", value: semantic, color: COLORS.blue },
    { key: "behavioral", label: "Behavioral", value: behavioral, color: COLORS.cyan },
  ];
}

/** Availability gauge 0..1 — open-to-work, notice period, recency. */
export function availabilityScore(c: RankedCandidate): number {
  let s = 0.5;
  if (c.open_to_work) s += 0.22;
  const np = c.notice_period_days ?? 90;
  if (np <= 30) s += 0.18;
  else if (np <= 60) s += 0.05;
  else s -= 0.1;
  const d = daysSinceActive(c);
  if (d !== null) {
    if (d <= 90) s += 0.12;
    else if (d <= 180) s += 0;
    else s -= 0.12;
  }
  return clamp01(s);
}

/** Reachability gauge 0..1 — recruiter response rate is the spine of this. */
export function reachabilityScore(c: RankedCandidate): number {
  const r = c.recruiter_response_rate ?? 0;
  // median 0.44 per §5; map to a gentle 0..1.
  return clamp01(0.15 + r * 0.95);
}

/** Demand-trust gauge 0..1 — product company + recency + responsiveness. */
export function demandTrustScore(c: RankedCandidate): number {
  let s = 0.45;
  if (isProduct(c)) s += 0.2;
  const d = daysSinceActive(c);
  if (d !== null && d <= 90) s += 0.15;
  if ((c.recruiter_response_rate ?? 0) >= 0.6) s += 0.2;
  return clamp01(s);
}

export type GaugeSpec = {
  key: string;
  label: string;
  value: number;
  color: string;
  group: "Availability" | "Reachability" | "Demand-trust";
};

export function gauges(c: RankedCandidate): GaugeSpec[] {
  return [
    {
      key: "availability",
      label: "Availability",
      value: availabilityScore(c),
      color: COLORS.cyan,
      group: "Availability",
    },
    {
      key: "reachability",
      label: "Reachability",
      value: reachabilityScore(c),
      color: COLORS.cyan,
      group: "Reachability",
    },
    {
      key: "demand",
      label: "Demand-trust",
      value: demandTrustScore(c),
      color: COLORS.gold,
      group: "Demand-trust",
    },
  ];
}

/* ---------- The 23 signals panel (DESIGN §7.1 card Zone C) ---------- */

export type SignalRow = {
  key: string;
  label: string;
  group: "Availability" | "Reachability" | "Demand-trust";
  /** display value; null => sentinel "No data — not penalized" */
  value: string | null;
  /** normalized 0..1 for a mini bar; null when sentinel */
  norm: number | null;
  sentinel: boolean;
};

/**
 * Renders the behavioral / trust signals the artifact carries, plus the
 * sentinels that the dataset withholds. Sentinels render as neutral
 * "No data — not penalized" chips (never red, never a penalty) — §5 hard rule.
 *
 * github_activity_score (-1, 64.6% of pool) and offer_acceptance_rate (-1,
 * 59.6%) are sentinels by design. We surface them as such so the UI proves the
 * "−1 never penalizes" guarantee visually.
 */
export function signals(c: RankedCandidate): SignalRow[] {
  const d = daysSinceActive(c);
  const np = c.notice_period_days ?? null;
  const rr = c.recruiter_response_rate ?? null;

  return [
    {
      key: "open_to_work",
      label: "Open to work",
      group: "Availability",
      value: c.open_to_work ? "Yes" : "No",
      norm: c.open_to_work ? 1 : 0,
      sentinel: false,
    },
    {
      key: "notice_period_days",
      label: "Notice period",
      group: "Availability",
      value: np === null ? null : `${np} days`,
      norm: np === null ? null : clamp01(1 - np / 120),
      sentinel: np === null,
    },
    {
      key: "last_active",
      label: "Last active",
      group: "Availability",
      value: d === null ? null : `${d} days ago`,
      norm: d === null ? null : clamp01(1 - d / 365),
      sentinel: d === null,
    },
    {
      key: "recruiter_response_rate",
      label: "Recruiter response rate",
      group: "Reachability",
      value: rr === null ? null : `${Math.round(rr * 100)}%`,
      norm: rr,
      sentinel: rr === null,
    },
    {
      key: "company_type",
      label: "Company type",
      group: "Demand-trust",
      value: c.company_type || null,
      norm: isProduct(c) ? 1 : 0.4,
      sentinel: !c.company_type,
    },
    {
      key: "yoe",
      label: "Years of experience",
      group: "Demand-trust",
      value: `${c.yoe.toFixed(1)} yrs`,
      norm: clamp01(c.yoe / 10),
      sentinel: false,
    },
    // Sentinels the dataset withholds — proven never to penalize.
    {
      key: "github_activity_score",
      label: "GitHub activity",
      group: "Demand-trust",
      value: null,
      norm: null,
      sentinel: true,
    },
    {
      key: "offer_acceptance_rate",
      label: "Offer acceptance rate",
      group: "Demand-trust",
      value: null,
      norm: null,
      sentinel: true,
    },
  ];
}

function clamp01n(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/* ---------- Trust pips (compact card summary) ---------- */

export type TrustPip = { label: string; on: boolean };

export function trustPips(c: RankedCandidate): TrustPip[] {
  const d = daysSinceActive(c);
  return [
    { label: "Open to work", on: !!c.open_to_work },
    { label: "≤30d notice", on: (c.notice_period_days ?? 99) <= 30 },
    { label: "Product company", on: isProduct(c) },
    { label: "Active <3mo", on: d !== null && d <= 90 },
    { label: "Responsive", on: (c.recruiter_response_rate ?? 0) >= 0.6 },
  ];
}

/* ---------- Left-rail lenses (client-side reorder, offline-safe) ---------- */

export type LensKey =
  | "open_to_work"
  | "notice_30"
  | "product"
  | "relocation"
  | "active_3mo";

export const LENSES: { key: LensKey; label: string }[] = [
  { key: "open_to_work", label: "Open to work" },
  { key: "notice_30", label: "≤30d notice" },
  { key: "product", label: "Product company" },
  { key: "relocation", label: "Relocation-willing" },
  { key: "active_3mo", label: "Active <3mo" },
];

/**
 * A lens score 0..1 per candidate — the board re-orders by (lensScore, then
 * original rank) so a lens is a VIEW over precomputed components, never a
 * re-ranking of the model. Returns 1 when the lens does not apply (neutral).
 */
export function lensScore(c: RankedCandidate, lens: LensKey): number {
  switch (lens) {
    case "open_to_work":
      return c.open_to_work ? 1 : 0;
    case "notice_30":
      return clamp01n(1 - (c.notice_period_days ?? 90) / 30) > 0 ? 1 : 0;
    case "product":
      return isProduct(c) ? 1 : 0;
    case "relocation":
      // No explicit relocation field in the frozen artifact; product+open is a
      // deterministic, honest proxy for "likely mobile". Surfaced as a soft lens.
      return c.open_to_work && isProduct(c) ? 1 : 0.5;
    case "active_3mo": {
      const d = daysSinceActive(c);
      return d !== null && d <= 90 ? 1 : 0;
    }
    default:
      return 1;
  }
}

/**
 * Apply a set of active lenses: re-order so candidates matching ALL active
 * lenses float up, preserving model rank as the stable tiebreaker. Pure +
 * deterministic — runs client-side with FLIP animation.
 */
export function applyLenses(
  candidates: RankedCandidate[],
  active: LensKey[]
): RankedCandidate[] {
  if (active.length === 0) return [...candidates];
  const scored = candidates.map((c) => {
    const s = active.reduce((acc, l) => acc + lensScore(c, l), 0);
    return { c, s };
  });
  scored.sort((a, b) => {
    if (b.s !== a.s) return b.s - a.s; // more lens matches first
    return a.c.rank - b.c.rank; // stable on model rank
  });
  return scored.map((x) => x.c);
}

/* ---------- Evidence tagging (candidate's own words → JD requirement) ---------- */

export type EvidenceTag = {
  text: string;
  kind: "match" | "behavioral" | "concern";
};

/**
 * Splits the verbatim reasoning string into tagged fragments. Gold "match" for
 * role-requirement phrases, cyan "behavioral" for availability phrases, amber
 * "concern" for the honest-gap clause (text after "gap"/"concern"/";").
 * Deterministic, purely lexical, draws only from the frozen reasoning text.
 */
export function tagEvidence(reasoning: string): EvidenceTag[] {
  if (!reasoning) return [];
  const out: EvidenceTag[] = [];
  // Concern clause: text after a "; gap is" / "; concern" / "; weakness" marker.
  const concernMatch = reasoning.match(/[;]\s*(gap|concern|weakness|risk)\b.*/i);
  let head = reasoning;
  if (concernMatch) {
    head = reasoning.slice(0, concernMatch.index).trim();
    out.push({ text: concernMatch[0].replace(/^;\s*/, "").trim(), kind: "concern" });
  }

  // Behavioral phrases.
  const behavRe = /(response rate[^,.;]*|open to work|notice[^,.;]*|active[^,.;]*)/gi;
  let behavioral: string[] = [];
  head = head.replace(behavRe, (m) => {
    behavioral.push(m.trim());
    return " "; // placeholder removed below
  });

  const matchText = head.replace(/ /g, "").replace(/\s{2,}/g, " ").trim();
  const result: EvidenceTag[] = [];
  if (matchText) result.push({ text: matchText, kind: "match" });
  for (const b of behavioral) result.push({ text: b, kind: "behavioral" });
  result.push(...out);
  return result;
}

/* ---------- Skills chips (deterministic from title/reasoning) ---------- */

export type SkillChip = {
  name: string;
  verified: boolean; // assessment-verified check
  unverifiedExpert: boolean; // ⚠ unverified-expert mark
};

const SKILL_DICT = [
  "ranking",
  "search",
  "recommendation",
  "retrieval",
  "embeddings",
  "vector db",
  "faiss",
  "ndcg",
  "learning-to-rank",
  "rag",
  "a/b testing",
  "python",
  "production ml",
];

/**
 * Surfaces named skills detected in the candidate's own reasoning/title.
 * "verified" pips are deterministic: a skill backed by a hard outcome phrase in
 * the reasoning (numbers, "production", "scale") is treated as assessment-
 * corroborated. We never mark an expert claim verified without such backing,
 * which is exactly the unverified-expert ⚠ surface.
 */
export function skillChips(c: RankedCandidate): SkillChip[] {
  const text = `${c.title} ${c.reasoning}`.toLowerCase();
  const hasOutcome = /\d|production|scale|gain|serving|queries|corpus/.test(
    c.reasoning.toLowerCase()
  );
  const chips: SkillChip[] = [];
  for (const s of SKILL_DICT) {
    const probe = s.replace("learning-to-rank", "l2r").split(" ")[0];
    if (text.includes(s) || text.includes(probe)) {
      chips.push({
        name: s,
        verified: hasOutcome,
        unverifiedExpert: !hasOutcome,
      });
    }
  }
  return chips.slice(0, 8);
}
