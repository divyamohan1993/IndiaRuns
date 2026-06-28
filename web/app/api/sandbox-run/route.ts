/**
 * Spec alias for the judge-mode sandbox runner. Delegates to the canonical
 * /api/sandbox handler so there is a single source of truth for the real
 * rank.py invocation (network-disabled subprocess + wall-clock timer + vendored
 * validator). See app/api/sandbox/route.ts for the implementation.
 */
export { POST } from "../sandbox/route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
