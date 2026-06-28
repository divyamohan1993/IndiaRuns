"use client";

import { useState } from "react";

/**
 * Generates a grounded outreach note for a candidate (by rank). Calls
 * /api/outreach which builds a deterministic draft from the candidate's frozen
 * reasoning and polishes tone via the live backend when a key is present. Works
 * offline (the draft itself is returned). Copy-to-clipboard included.
 */
export function OutreachButton({ rank }: { rank: number }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function gen() {
    setBusy(true);
    setCopied(false);
    try {
      const res = await fetch("/api/outreach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rank }),
      });
      const json = (await res.json()) as { text?: string };
      setText(json.text || "");
    } catch {
      setText("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        onClick={gen}
        disabled={busy}
        className="rounded-lg border border-cyan/40 bg-cyan/10 px-3 py-2 text-sm text-cyan transition hover:bg-cyan/20 disabled:opacity-60"
      >
        {busy ? "Drafting…" : "Draft outreach"}
      </button>
      {text && (
        <div className="mt-3 rounded-xl border border-glass-border bg-glass-fill p-3">
          <p className="whitespace-pre-wrap text-sm text-ink">{text}</p>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(text);
              setCopied(true);
            }}
            className="mt-2 text-xs text-ink-mute underline hover:text-ink"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      )}
    </div>
  );
}
