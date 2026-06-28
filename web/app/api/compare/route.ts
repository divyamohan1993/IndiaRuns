import { NextResponse } from "next/server";
import { loadRanked, loadIntent } from "@/lib/artifacts";
import { compare } from "@/lib/ai/copilot-tools";
import { generate } from "@/lib/ai/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Side-by-side compare synthesis. The deterministic compare tool builds the
 * matrix + a baseline "ATLAS's call"; the live backend, when present, sharpens
 * the one-line synthesis. Facts are pre-grounded so it is safe offline.
 */
export async function POST(req: Request) {
  let ranks: number[] = [1, 2];
  try {
    const body = (await req.json()) as { ranks?: number[] };
    if (Array.isArray(body.ranks) && body.ranks.length >= 2)
      ranks = body.ranks.slice(0, 4);
  } catch {
    /* default 1,2 */
  }

  const ranked = loadRanked();
  const intent = loadIntent();
  const result = compare(ranked.candidates, ranks);

  const system =
    `For the ${intent.job_title} role, write ONE sentence naming which ` +
    "candidate ATLAS should advance and why. Use ONLY facts in the text below.";
  const { text, backend } = await generate({
    system,
    user: result.text,
    maxChars: 240,
    fallback: () => {
      const call = result.text.split("ATLAS's call:")[1];
      return call ? "ATLAS's call:" + call : result.text;
    },
  });

  return NextResponse.json({ ranks, ids: result.ids, matrix: result.text, synthesis: text, backend });
}
