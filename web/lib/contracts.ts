import { z } from "zod";

/**
 * Zod contract for the FROZEN Plane-A web artifacts under web/public/artifacts/.
 * These files are produced by precompute/build_web_artifacts.py from the SAME
 * code path that writes the graded submission.csv, so ranked_top100.json is
 * provably the submission. The web spine never recomputes — it consumes.
 *
 * Every schema is permissive on extra keys (.passthrough is NOT used so we stay
 * strict on shape) but tolerant on optional enrichment fields that may be added
 * later. Parsing failures surface loudly in dev and fall back to [] in prod.
 */

const candidateIdRe = /^CAND_[0-9]{7}$/;

/* ---------- intent.json ---------- */

export const IntentChipSchema = z.object({
  label: z.string(),
  kind: z.enum(["must", "anti", "behavioral"]),
});
export type IntentChip = z.infer<typeof IntentChipSchema>;

export const IntentSchema = z.object({
  job_title: z.string(),
  company: z.string(),
  must_haves: z.array(IntentChipSchema),
  anti_patterns: z.array(IntentChipSchema),
  behavioral: z.array(IntentChipSchema),
  clause_count: z.number().int().nonnegative(),
});
export type Intent = z.infer<typeof IntentSchema>;

/* ---------- ranked_top100.json ---------- */

export const RankedCandidateSchema = z.object({
  rank: z.number().int().min(1),
  candidate_id: z.string().regex(candidateIdRe),
  score: z.number(),
  reasoning: z.string(),
  title: z.string(),
  company: z.string(),
  industry: z.string().optional().default(""),
  yoe: z.number().nonnegative(),
  company_type: z.string(), // "product" | "services" | ...
  recruiter_response_rate: z.number().optional().default(0),
  open_to_work: z.boolean().optional().default(false),
  notice_period_days: z.number().optional().default(90),
  last_active_date: z.string().optional().default(""),
});
export type RankedCandidate = z.infer<typeof RankedCandidateSchema>;

export const RankedTop100Schema = z.object({
  job_title: z.string(),
  count: z.number().int(),
  candidates: z.array(RankedCandidateSchema),
});
export type RankedTop100 = z.infer<typeof RankedTop100Schema>;

/* ---------- funnel.json ---------- */

export const FunnelStageSchema = z.object({
  name: z.string(),
  count: z.number().int().nonnegative(),
});

export const RecallTierSchema = z.object({
  in_shortlist: z.number().int().nonnegative(),
  recall: z.number(),
  total: z.number().int().nonnegative(),
});

export const FunnelSchema = z.object({
  stages: z.array(FunnelStageSchema),
  recall_gate: z.object({
    tier5: RecallTierSchema,
    tier4: RecallTierSchema,
    gate_passed: z.boolean(),
    K: z.number().int(),
  }),
  honeypot_burn: z.object({
    total: z.number().int(),
    signature_counts: z.record(z.string(), z.number().int()),
    ids: z.array(z.string()),
  }),
  projection: z.array(
    z.object({
      candidate_id: z.string(),
      rank: z.number().int(),
      x: z.number(),
      y: z.number(),
    })
  ),
});
export type Funnel = z.infer<typeof FunnelSchema>;

/* ---------- rejected_traps.json ---------- */

export const TrapSignatureSchema = z.object({
  signature: z.string(),
  count: z.number().int(),
  why_fatal: z.string(),
  examples: z.array(z.string()),
});

export const RejectedTrapsSchema = z.object({
  headline: z.string(),
  signatures: z.array(TrapSignatureSchema),
  not_a_trap: z.object({
    signature: z.string(),
    fires_on: z.number().int(),
    note: z.string(),
  }),
  soft_demoted: z.record(z.string(), z.number().int()),
  baseline_foil: z.object({ note: z.string() }),
});
export type RejectedTraps = z.infer<typeof RejectedTrapsSchema>;
