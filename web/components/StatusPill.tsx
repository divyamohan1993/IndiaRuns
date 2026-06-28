import { cn } from "@/lib/utils";

/**
 * Honest AI status pill. Live ● (cyan) when a generation backend key is present;
 * Offline ○ (muted) when the deterministic brain is in charge. Never lies —
 * the spine works either way.
 */
export function StatusPill({ live }: { live: boolean }) {
  return (
    <span
      role="status"
      aria-label={live ? "Live AI backend connected" : "Offline AI — deterministic brain"}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider",
        live
          ? "border-cyan/40 bg-cyan/10 text-cyan"
          : "border-glass-border bg-glass-fill text-ink-mute"
      )}
    >
      <span aria-hidden>{live ? "●" : "○"}</span>
      {live ? "Live AI" : "Offline AI"}
    </span>
  );
}
