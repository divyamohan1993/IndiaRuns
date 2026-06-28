import { cn } from "@/lib/utils";
import type { IntentChip as IntentChipT } from "@/lib/contracts";

/**
 * Intent chip. Must-haves are gold, anti-patterns are struck-through red,
 * behavioral prefs are cyan. Meaning is carried by the leading glyph + text, not
 * color alone (✓ / ✕ / ◷), satisfying the no-color-only rule.
 */
export function IntentChip({ chip }: { chip: IntentChipT }) {
  const styles = {
    must: "border-gold/40 bg-gold/10 text-gold",
    anti: "border-trap/40 bg-trap/10 text-trap line-through decoration-trap/70",
    behavioral: "border-cyan/40 bg-cyan/10 text-cyan",
  }[chip.kind];

  const glyph = { must: "✓", anti: "✕", behavioral: "◷" }[chip.kind];
  const aria = {
    must: "Must-have",
    anti: "Anti-pattern, excluded",
    behavioral: "Behavioral preference",
  }[chip.kind];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm",
        styles
      )}
    >
      <span aria-hidden className="no-underline">
        {glyph}
      </span>
      <span className="sr-only">{aria}: </span>
      {chip.label}
    </span>
  );
}
