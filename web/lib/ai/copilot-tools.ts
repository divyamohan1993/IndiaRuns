import type { RankedCandidate } from "@/lib/contracts";
import {
  isProduct,
  daysSinceActive,
  availabilityScore,
  reachabilityScore,
  fitComponents,
} from "@/lib/derive";

/**
 * Co-Pilot tool layer. A small, deterministic intent router + four tools that
 * operate over the shipped top-100 ONLY (no hallucination surface beyond the
 * frozen facts). filter / lens / sort / compare / summarize / list run with NO
 * LLM. explain / outreach produce a grounded deterministic draft that the live
 * backend may polish — but the facts always come from these functions, so a
 * key-less product is fully functional.
 *
 * The router is intentionally rule-based (keyword + number extraction). It is a
 * tool-CALLING surface: each branch returns a structured ToolResult the UI can
 * render, plus a `needsLLM` hint for explain/outreach.
 */

export type ToolName =
  | "list_top"
  | "get_candidate"
  | "compare"
  | "apply_lens"
  | "explain"
  | "outreach";

export type ToolResult = {
  tool: ToolName;
  /** Human-readable answer (always deterministic + grounded). */
  text: string;
  /** Candidate ids this answer references (for the UI to highlight/link). */
  ids: string[];
  /** When true, the live backend may rewrite `text` for tone (facts unchanged). */
  needsLLM: boolean;
};

function byRank(a: RankedCandidate, b: RankedCandidate) {
  return a.rank - b.rank;
}

function fmtCand(c: RankedCandidate): string {
  return `#${c.rank} ${titleCase(c.title)} @ ${c.company} (${c.yoe.toFixed(
    1
  )}y, ${isProduct(c) ? "product" : "services"})`;
}

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (m) => m.toUpperCase());
}

/** Pull a rank number out of free text ("rank 3", "#3", "number 3"). */
function extractRanks(q: string): number[] {
  const out: number[] = [];
  const re = /(?:rank|#|number|no\.?|candidate)\s*#?\s*(\d{1,3})/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(q)) !== null) {
    const n = Number(m[1]);
    if (n >= 1 && n <= 100) out.push(n);
  }
  // Bare "3 and 4" style for compare.
  if (out.length === 0) {
    const bare = q.match(/\b(\d{1,3})\b/g);
    if (bare) for (const b of bare) {
      const n = Number(b);
      if (n >= 1 && n <= 100) out.push(n);
    }
  }
  return [...new Set(out)];
}

/* ---------- tools ---------- */

export function listTop(
  candidates: RankedCandidate[],
  n: number
): ToolResult {
  const top = [...candidates].sort(byRank).slice(0, n);
  return {
    tool: "list_top",
    text:
      `Top ${top.length}:\n` + top.map((c) => "• " + fmtCand(c)).join("\n"),
    ids: top.map((c) => c.candidate_id),
    needsLLM: false,
  };
}

export function getCandidate(
  candidates: RankedCandidate[],
  rank: number
): ToolResult {
  const c = candidates.find((x) => x.rank === rank);
  if (!c)
    return {
      tool: "get_candidate",
      text: `No candidate at rank ${rank} in the top 100.`,
      ids: [],
      needsLLM: false,
    };
  return {
    tool: "get_candidate",
    text: `${fmtCand(c)}\n${c.reasoning}`,
    ids: [c.candidate_id],
    needsLLM: false,
  };
}

export function applyLensFilter(
  candidates: RankedCandidate[],
  q: string
): ToolResult {
  const ql = q.toLowerCase();
  let pred: (c: RankedCandidate) => boolean = () => true;
  let label = "all";
  if (/product/.test(ql)) {
    pred = isProduct;
    label = "product-company";
  } else if (/open to work|open-to-work/.test(ql)) {
    pred = (c) => !!c.open_to_work;
    label = "open-to-work";
  } else if (/notice|30 ?day|join/.test(ql)) {
    pred = (c) => (c.notice_period_days ?? 99) <= 30;
    label = "≤30-day notice";
  } else if (/active|recent/.test(ql)) {
    pred = (c) => {
      const d = daysSinceActive(c);
      return d !== null && d <= 90;
    };
    label = "active <3mo";
  } else if (/responsive|respond/.test(ql)) {
    pred = (c) => (c.recruiter_response_rate ?? 0) >= 0.6;
    label = "responsive";
  }
  const hits = [...candidates].filter(pred).sort(byRank);
  return {
    tool: "apply_lens",
    text:
      `${hits.length} ${label} candidate${hits.length === 1 ? "" : "s"}:\n` +
      hits
        .slice(0, 12)
        .map((c) => "• " + fmtCand(c))
        .join("\n") +
      (hits.length > 12 ? `\n…and ${hits.length - 12} more` : ""),
    ids: hits.map((c) => c.candidate_id),
    needsLLM: false,
  };
}

export function compare(
  candidates: RankedCandidate[],
  ranks: number[]
): ToolResult {
  const picks = ranks
    .map((r) => candidates.find((c) => c.rank === r))
    .filter((c): c is RankedCandidate => !!c);
  if (picks.length < 2)
    return {
      tool: "compare",
      text: "Give me two ranks to compare, e.g. 'compare rank 1 and rank 2'.",
      ids: picks.map((c) => c.candidate_id),
      needsLLM: false,
    };
  const lines = picks.map((c) => {
    const comp = fitComponents(c);
    const ev = comp.find((x) => x.key === "evidence")?.value ?? 0;
    const beh = comp.find((x) => x.key === "behavioral")?.value ?? 0;
    return `${fmtCand(c)}\n   evidence ${(ev * 100) | 0} · behavioral ${
      (beh * 100) | 0
    } · response ${Math.round((c.recruiter_response_rate ?? 0) * 100)}%`;
  });
  // Deterministic "ATLAS's call".
  const lead = [...picks].sort(byRank)[0];
  const call = `ATLAS's call: ${titleCase(lead.title)} @ ${
    lead.company
  } leads — higher graded fit and ${
    availabilityScore(lead) >= 0.6 ? "strong availability" : "solid evidence"
  }.`;
  return {
    tool: "compare",
    text: lines.join("\n") + "\n\n" + call,
    ids: picks.map((c) => c.candidate_id),
    needsLLM: false,
  };
}

/** explain / outreach return a grounded draft the live backend may polish. */
export function explainDraft(
  candidates: RankedCandidate[],
  rank: number
): ToolResult {
  const c = candidates.find((x) => x.rank === rank) ?? candidates[0];
  return {
    tool: "explain",
    text: `${fmtCand(c)} — ${c.reasoning} Availability ${(
      availabilityScore(c) * 100
    ).toFixed(0)}/100, reachability ${(reachabilityScore(c) * 100).toFixed(
      0
    )}/100.`,
    ids: [c.candidate_id],
    needsLLM: true,
  };
}

export function outreachDraft(
  candidates: RankedCandidate[],
  rank: number,
  jobTitle: string
): ToolResult {
  const c = candidates.find((x) => x.rank === rank) ?? candidates[0];
  const draft =
    `Hi — we're hiring a ${jobTitle} and your work on ` +
    `${firstClause(c.reasoning)} stood out. ` +
    `Given your background at ${c.company}, I'd love to share more. Open to a quick chat?`;
  return {
    tool: "outreach",
    text: draft,
    ids: [c.candidate_id],
    needsLLM: true,
  };
}

function firstClause(reasoning: string): string {
  const m = reasoning.split(/[;,.]/)[0];
  return (m || reasoning).trim().toLowerCase();
}

/* ---------- router ---------- */

export function routeQuery(
  candidates: RankedCandidate[],
  query: string,
  jobTitle: string
): ToolResult {
  const q = query.trim();
  const ql = q.toLowerCase();
  const ranks = extractRanks(q);

  if (/\bcompare\b/.test(ql) || (ranks.length >= 2 && /\bvs\b|versus|and/.test(ql)))
    return compare(candidates, ranks.slice(0, 4));

  if (/outreach|message|reach out|email|note to/.test(ql))
    return outreachDraft(candidates, ranks[0] ?? 1, jobTitle);

  if (/why|explain|tell me about|reasoning|fit/.test(ql) && ranks.length)
    return explainDraft(candidates, ranks[0]);

  if (ranks.length === 1 && /who|show|get|candidate|rank|#/.test(ql))
    return getCandidate(candidates, ranks[0]);

  if (
    /product|open to work|open-to-work|notice|active|recent|responsive|only|filter|show/.test(
      ql
    )
  )
    return applyLensFilter(candidates, q);

  if (/top|best|list/.test(ql)) {
    const n = ranks[0] ?? 3;
    return listTop(candidates, Math.min(n || 3, 50));
  }

  // Default: a grounded top-3 summary.
  return listTop(candidates, 3);
}
