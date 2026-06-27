import { tagEvidence } from "@/lib/derive";
import { cn } from "@/lib/utils";

/**
 * Renders the verbatim reasoning, then a tagged breakdown: gold = JD match,
 * blue = behavioral, amber = honest concern. Meaning carried by a label, not
 * color alone.
 */
export function EvidenceBlock({ reasoning }: { reasoning: string }) {
  const tags = tagEvidence(reasoning);
  const styles = {
    match: { dot: "bg-gold", text: "text-ink", label: "JD match" },
    behavioral: { dot: "bg-cyan", text: "text-ink", label: "Behavioral" },
    concern: { dot: "bg-[#F5A04E]", text: "text-ink", label: "Honest concern" },
  } as const;

  return (
    <div className="space-y-4">
      <blockquote className="rounded-xl border-l-2 border-gold/60 bg-glass-fill p-4 text-sm italic leading-relaxed text-ink">
        “{reasoning}”
        <footer className="mt-2 not-italic text-[11px] text-ink-faint">
          Verbatim submission reasoning — the UI is the submission.
        </footer>
      </blockquote>

      <ul className="space-y-2">
        {tags.map((t, i) => {
          const s = styles[t.kind];
          return (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span
                className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", s.dot)}
                aria-hidden
              />
              <span>
                <span className="mr-2 font-mono text-[10px] uppercase tracking-wide text-ink-faint">
                  {s.label}
                </span>
                <span className={s.text}>{t.text}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
