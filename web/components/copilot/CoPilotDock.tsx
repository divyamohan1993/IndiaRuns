"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * Persistent Co-Pilot dock. This is the SPINE-STAGE placeholder: it renders,
 * opens/closes, shows suggested-prompt chips and the honest status, and is wired
 * to a deterministic responder so it is functional offline. The tool-calling
 * agent (get_candidate / compare / apply_lens / list_top) is wired fully in the
 * next stage; the dock contract (open state, message list, status) is final here
 * so that stage is a drop-in.
 */

const SUGGESTED = [
  "Who are the top 3 and why?",
  "Show only product-company candidates",
  "Compare rank 1 and rank 2",
  "Which candidates have ≤30 day notice?",
];

type Msg = { role: "user" | "assistant"; text: string };

export function CoPilotDock({ live }: { live: boolean }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: "assistant",
      text: "I'm your recruiting co-pilot. I work over the shipped top-100 only — ask me to filter, compare, or explain a candidate.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setInput("");
    setBusy(true);
    try {
      // The Co-Pilot endpoint runs the deterministic tool router over the
      // shipped top-100 (filter/lens/sort/compare/list/get always work) and
      // only uses the live backend to polish explain/outreach tone.
      const res = await fetch("/api/copilot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: t }),
      });
      const json = (await res.json()) as { text?: string };
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text:
            json.text ||
            "I work over the shipped top-100 — try 'show product candidates' or 'compare rank 1 and 2'.",
        },
      ]);
    } catch {
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text:
            "Offline: filtering, lenses, sort, and compare run deterministically over the shipped top-100.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="copilot-panel"
        className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full border border-gold/40 bg-navy-800 px-4 py-3 font-mono text-sm text-gold shadow-glow transition hover:bg-navy-700"
      >
        <span aria-hidden>✦</span>
        Co-Pilot
        <span
          className={cn(
            "ml-1 h-2 w-2 rounded-full",
            live ? "bg-cyan" : "bg-ink-faint"
          )}
          aria-hidden
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.aside
            id="copilot-panel"
            role="complementary"
            aria-label="Recruiting co-pilot"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="glass fixed bottom-20 right-5 z-50 flex h-[28rem] w-[22rem] flex-col rounded-2xl shadow-glass"
          >
            <div className="flex items-center justify-between border-b border-glass-border px-4 py-3">
              <span className="font-mono text-xs uppercase tracking-wider text-gold">
                Co-Pilot
              </span>
              <span className="text-[11px] text-ink-mute">
                {live ? "Live AI ●" : "Offline AI ○"}
              </span>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
              {msgs.map((m, i) => (
                <div
                  key={i}
                  className={cn(
                    "max-w-[90%] whitespace-pre-wrap rounded-xl px-3 py-2",
                    m.role === "user"
                      ? "ml-auto bg-cyan/15 text-ink"
                      : "bg-glass-fill text-ink-mute"
                  )}
                >
                  {m.text}
                </div>
              ))}
            </div>

            <div className="border-t border-glass-border px-3 py-2">
              <div className="mb-2 flex flex-wrap gap-1.5">
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-glass-border bg-glass-fill px-2 py-1 text-[11px] text-ink-mute hover:text-ink"
                  >
                    {s}
                  </button>
                ))}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  send(input);
                }}
                className="flex gap-2"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask the co-pilot…"
                  aria-label="Message the co-pilot"
                  className="flex-1 rounded-lg border border-glass-border bg-navy-900 px-3 py-2 text-sm text-ink placeholder:text-ink-faint"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-lg bg-gold px-3 py-2 text-sm font-medium text-navy-900 disabled:opacity-60"
                >
                  {busy ? "…" : "Send"}
                </button>
              </form>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
