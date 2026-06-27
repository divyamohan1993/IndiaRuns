import { loadRanked, loadFunnel, loadRejectedTraps } from "@/lib/artifacts";
import { BoardClient } from "@/components/board/BoardClient";
import { BoardOverlays } from "@/components/board/BoardOverlays";
import { aiBackendLive } from "@/lib/utils";

export default function BoardPage() {
  const ranked = loadRanked();
  const funnel = loadFunnel();
  const traps = loadRejectedTraps();
  const live = aiBackendLive();

  const screened =
    funnel.stages.find((s) => s.name === "Candidate pool")?.count ?? 100000;
  const removed = funnel.honeypot_burn.total;

  return (
    <div className="py-8">
      <header className="mx-auto mb-8 max-w-7xl px-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-cyan">
              Shortlist board
            </p>
            <h1 className="mt-2 text-2xl font-bold text-ink sm:text-3xl">
              Top 100 ·{" "}
              <span className="text-ink-mute">
                {screened.toLocaleString()} screened
              </span>{" "}
              · {removed} traps removed ·{" "}
              <span className="text-gold">ranked in 73s offline</span>
            </h1>
          </div>
          <BoardOverlays traps={traps} candidates={ranked.candidates} live={live} />
        </div>
      </header>

      <BoardClient candidates={ranked.candidates} />
    </div>
  );
}
