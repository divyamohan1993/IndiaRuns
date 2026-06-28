import type { SignalRow } from "@/lib/derive";
import { cn } from "@/lib/utils";

/**
 * The 23-signals panel grouped into Availability / Reachability / Demand-trust.
 * Sentinels render as neutral "No data — not penalized" chips (never red, never
 * a penalty) — the §5 hard rule made visible.
 */
export function SignalsPanel({ signals }: { signals: SignalRow[] }) {
  const groups: SignalRow["group"][] = [
    "Availability",
    "Reachability",
    "Demand-trust",
  ];
  return (
    <div className="space-y-5">
      {groups.map((g) => {
        const rows = signals.filter((s) => s.group === g);
        if (rows.length === 0) return null;
        return (
          <div key={g}>
            <h3 className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-mute">
              {g}
            </h3>
            <ul className="space-y-2">
              {rows.map((s) => (
                <li
                  key={s.key}
                  className="flex items-center justify-between gap-3 rounded-lg border border-glass-border bg-glass-fill px-3 py-2"
                >
                  <span className="text-sm text-ink-mute">{s.label}</span>
                  {s.sentinel ? (
                    <span className="rounded-full border border-glass-border px-2 py-0.5 text-[11px] text-ink-faint">
                      No data — not penalized
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      {s.norm !== null && (
                        <span
                          className="h-1.5 w-14 overflow-hidden rounded-full bg-white/10"
                          role="meter"
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={Math.round((s.norm ?? 0) * 100)}
                          aria-label={`${s.label} ${Math.round((s.norm ?? 0) * 100)} of 100`}
                        >
                          <span
                            className={cn("block h-full rounded-full bg-cyan")}
                            style={{ width: `${(s.norm ?? 0) * 100}%` }}
                          />
                        </span>
                      )}
                      <span className="font-mono text-sm text-ink">
                        {s.value}
                      </span>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
