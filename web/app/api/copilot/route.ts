import { NextResponse } from "next/server";
import { loadRanked, loadIntent } from "@/lib/artifacts";
import { routeQuery } from "@/lib/ai/copilot-tools";
import { generate } from "@/lib/ai/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Co-Pilot endpoint. The deterministic tool router (filter/lens/sort/compare/
 * summarize/list/get) runs server-side over the shipped top-100 ONLY and always
 * returns a grounded answer. For explain/outreach (needsLLM) the live backend
 * polishes the tone of the deterministic draft — never inventing facts, since
 * the draft already contains them. With no key, the draft itself is returned.
 */
export async function POST(req: Request) {
  let query = "";
  try {
    const body = (await req.json()) as { query?: string; message?: string };
    query = (body.query ?? body.message ?? "").trim();
  } catch {
    /* empty */
  }
  if (!query) {
    return NextResponse.json({
      text: "Ask me to filter, compare, or explain a candidate from the top 100.",
      ids: [],
      tool: "list_top",
      backend: "offline",
    });
  }

  const ranked = loadRanked();
  const intent = loadIntent();
  const result = routeQuery(ranked.candidates, query, intent.job_title);

  if (!result.needsLLM) {
    return NextResponse.json({ ...result, backend: "offline" });
  }

  // Polish explain/outreach tone via the live backend (facts already grounded).
  const system =
    "You are a concise recruiting co-pilot. Rewrite the DRAFT below in a warm, " +
    "professional tone. Do NOT add any fact, skill, company, or number not " +
    "already in the draft. Keep it under 60 words.";
  const { text, backend } = await generate({
    system,
    user: `DRAFT:\n${result.text}`,
    maxChars: 420,
    fallback: () => result.text,
  });

  return NextResponse.json({ ...result, text, backend });
}
