import { NextResponse } from "next/server";
import { loadRanked, loadIntent } from "@/lib/artifacts";
import { outreachDraft } from "@/lib/ai/copilot-tools";
import { generate } from "@/lib/ai/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Outreach message generator for a single candidate (by rank). The deterministic
 * draft is grounded in the candidate's frozen reasoning; the live backend, when
 * present, polishes tone without adding facts. Works fully offline.
 */
export async function POST(req: Request) {
  let rank = 1;
  try {
    const body = (await req.json()) as { rank?: number };
    if (typeof body.rank === "number") rank = body.rank;
  } catch {
    /* default rank 1 */
  }

  const ranked = loadRanked();
  const intent = loadIntent();
  const draft = outreachDraft(ranked.candidates, rank, intent.job_title);

  const system =
    "Rewrite this recruiter outreach note to be warm and specific. Do NOT add " +
    "any fact/skill/company/number not already present. Keep it under 70 words.";
  const { text, backend } = await generate({
    system,
    user: draft.text,
    maxChars: 480,
    fallback: () => draft.text,
  });

  return NextResponse.json({ rank, ids: draft.ids, text, backend });
}
