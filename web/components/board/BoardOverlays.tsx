"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { RankedCandidate, RejectedTraps } from "@/lib/contracts";
import { RejectedTrapsDrawer } from "./RejectedTrapsDrawer";
import { CompareDrawer } from "./CompareDrawer";

/**
 * Board action bar + URL-param-driven overlays. Mounts the rejected-traps and
 * compare drawers and auto-opens them when the board is reached via
 * /board?rejected or /board?compare (deep-linkable from the cinema / share).
 * useSearchParams is wrapped in Suspense per Next 14 App Router requirements.
 */
function Inner({
  traps,
  candidates,
  live,
}: {
  traps: RejectedTraps;
  candidates: RankedCandidate[];
  live: boolean;
}) {
  const params = useSearchParams();
  const [rejConsumed, setRejConsumed] = useState(false);
  const [cmpConsumed, setCmpConsumed] = useState(false);

  const wantRejected = params.has("rejected") && !rejConsumed;
  const wantCompare = params.has("compare") && !cmpConsumed;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <CompareDrawer
        candidates={candidates}
        live={live}
        openSignal={wantCompare}
        onConsumeSignal={() => setCmpConsumed(true)}
      />
      <RejectedTrapsDrawer
        traps={traps}
        openSignal={wantRejected}
        onConsumeSignal={() => setRejConsumed(true)}
      />
    </div>
  );
}

export function BoardOverlays(props: {
  traps: RejectedTraps;
  candidates: RankedCandidate[];
  live: boolean;
}) {
  return (
    <Suspense fallback={null}>
      <Inner {...props} />
    </Suspense>
  );
}
