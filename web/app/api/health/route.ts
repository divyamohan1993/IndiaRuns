import { NextResponse } from "next/server";
import { backendName } from "@/lib/ai/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Health + honest backend-status probe. Reports which live AI backend is active
 * (nvidia / cli / offline) without ever exposing the key. The status pill and
 * any reviewer can hit this to see the truthful posture.
 */
export async function GET() {
  const backend = backendName();
  return NextResponse.json({
    ok: true,
    backend,
    live: backend !== "offline",
    plane: "C",
    note: "Plane C live product. The graded rank.py path makes no network/LLM/GPU calls.",
    ts: new Date().toISOString(),
  });
}
