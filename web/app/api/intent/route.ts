import { NextResponse } from "next/server";
import { loadIntent } from "@/lib/artifacts";
import { generate, backendName } from "@/lib/ai/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Live JD → intent decomposition. With a backend key, it asks the model to
 * surface must-haves / anti-patterns / behavioral prefs for an arbitrary JD.
 * With no key it returns the frozen intent.json (the Redrob decomposition) —
 * always valid, always grounded. The response shape matches IntentSchema so the
 * client renders identically either way.
 */
export async function POST(req: Request) {
  const frozen = loadIntent();
  let jd = "";
  try {
    const body = (await req.json()) as { jd?: string };
    jd = (body.jd ?? "").trim();
  } catch {
    /* no body → frozen */
  }

  // No custom JD (or it matches the default) → ship the frozen decomposition.
  if (!jd || jd.length < 40) {
    return NextResponse.json({ ...frozen, backend: "offline", source: "frozen" });
  }

  const system =
    "You decompose a hiring JD into structured chips. Return ONLY JSON: " +
    '{"must_haves":[{"label":string}],"anti_patterns":[{"label":string}],' +
    '"behavioral":[{"label":string}]}. Labels <= 48 chars. Use only the JD text.';

  const { text, backend } = await generate({
    system,
    user: jd.slice(0, 4000),
    maxChars: 1400,
    fallback: () => JSON.stringify(frozen),
  });

  // Parse the model output; on any failure fall back to frozen.
  try {
    const parsed = JSON.parse(extractJson(text)) as {
      must_haves?: { label: string }[];
      anti_patterns?: { label: string }[];
      behavioral?: { label: string }[];
    };
    const must = (parsed.must_haves ?? []).map((c) => ({
      label: String(c.label).slice(0, 48),
      kind: "must" as const,
    }));
    const anti = (parsed.anti_patterns ?? []).map((c) => ({
      label: String(c.label).slice(0, 48),
      kind: "anti" as const,
    }));
    const beh = (parsed.behavioral ?? []).map((c) => ({
      label: String(c.label).slice(0, 48),
      kind: "behavioral" as const,
    }));
    if (must.length === 0) throw new Error("empty");
    return NextResponse.json({
      job_title: frozen.job_title,
      company: frozen.company,
      must_haves: must,
      anti_patterns: anti,
      behavioral: beh,
      clause_count: must.length + anti.length + beh.length,
      backend,
      source: "live",
    });
  } catch {
    return NextResponse.json({ ...frozen, backend: backendName(), source: "frozen-fallback" });
  }
}

function extractJson(s: string): string {
  const a = s.indexOf("{");
  const b = s.lastIndexOf("}");
  return a >= 0 && b > a ? s.slice(a, b + 1) : "{}";
}
