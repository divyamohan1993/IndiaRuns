import type { SkillChip } from "@/lib/derive";
import { cn } from "@/lib/utils";

/**
 * Skills as chips. Assessment-verified chips carry a ✓; an expert claim with no
 * corroborating outcome carries a ⚠ unverified-expert mark.
 */
export function SkillChips({ chips }: { chips: SkillChip[] }) {
  if (chips.length === 0) {
    return (
      <p className="text-sm text-ink-faint">
        No named skills surfaced from the candidate&apos;s evidence.
      </p>
    );
  }
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((s) => (
        <span
          key={s.name}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs capitalize",
            s.verified
              ? "border-gold/40 bg-gold/10 text-gold"
              : "border-[#F5A04E]/40 bg-[#F5A04E]/10 text-[#F5A04E]"
          )}
        >
          {s.verified ? (
            <span aria-label="Assessment-verified" title="Assessment-verified">
              ✓
            </span>
          ) : (
            <span aria-label="Unverified expert claim" title="Unverified expert claim">
              ⚠
            </span>
          )}
          {s.name}
        </span>
      ))}
    </div>
  );
}
