import fs from "node:fs";
import path from "node:path";
import {
  IntentSchema,
  RankedTop100Schema,
  FunnelSchema,
  RejectedTrapsSchema,
  type Intent,
  type RankedTop100,
  type Funnel,
  type RejectedTraps,
  type RankedCandidate,
} from "./contracts";

/**
 * Server-side artifact loader. Reads the frozen JSON shipped under
 * web/public/artifacts and validates it against the Zod contract. These files
 * are committed; reads happen at request/render time on the server (App Router
 * Server Components), never in the browser bundle.
 */

const ARTIFACT_DIR = path.join(process.cwd(), "public", "artifacts");

function readJson(name: string): unknown {
  const p = path.join(ARTIFACT_DIR, name);
  const raw = fs.readFileSync(p, "utf-8");
  return JSON.parse(raw);
}

export function loadIntent(): Intent {
  return IntentSchema.parse(readJson("intent.json"));
}

export function loadRanked(): RankedTop100 {
  return RankedTop100Schema.parse(readJson("ranked_top100.json"));
}

export function loadFunnel(): Funnel {
  return FunnelSchema.parse(readJson("funnel.json"));
}

export function loadRejectedTraps(): RejectedTraps {
  return RejectedTrapsSchema.parse(readJson("rejected_traps.json"));
}

export function getCandidateByRank(rank: number): RankedCandidate | undefined {
  const ranked = loadRanked();
  return ranked.candidates.find((c) => c.rank === rank);
}
