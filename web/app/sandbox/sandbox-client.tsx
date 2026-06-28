"use client";

import { useRef, useState } from "react";

type Result = {
  wallMs: number;
  exitCode: number;
  csv: string;
  validator: string;
};

/**
 * Judge-mode client. POSTs to /api/sandbox, parses the SSE stream, and renders
 * the live rank.py log, the wall-clock timer, the produced CSV, and the
 * validator output. The button is the proof: the REAL pipeline, offline,
 * in-container, reproducible.
 */
export function SandboxClient() {
  const [running, setRunning] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [meta, setMeta] = useState<{ cmd: string; network: string } | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  async function run() {
    setRunning(true);
    setLines([]);
    setResult(null);
    setMeta(null);

    const res = await fetch("/api/sandbox", { method: "POST" });
    if (!res.body) {
      setLines(["ERROR: no response stream"]);
      setRunning(false);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    // Minimal SSE parser.
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop() ?? "";
      for (const ev of events) {
        const evMatch = ev.match(/^event: (.+)$/m);
        const dataMatch = ev.match(/^data: (.+)$/m);
        if (!dataMatch) continue;
        let data: any;
        try {
          data = JSON.parse(dataMatch[1]);
        } catch {
          continue;
        }
        const type = evMatch?.[1] ?? "line";
        if (type === "meta") setMeta(data);
        else if (type === "line") setLines((l) => [...l, data.line]);
        else if (type === "result") setResult(data as Result);
        else if (type === "done") setRunning(false);
      }
      requestAnimationFrame(() => {
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
      });
    }
    setRunning(false);
  }

  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl p-6 shadow-glass">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              Run the real rank.py on a 100-candidate sample
            </h2>
            <p className="mt-1 text-sm text-ink-mute">
              Same code that writes the graded submission. Network disabled.
              Wall-clock timed. CPU-only.
            </p>
          </div>
          <button
            onClick={run}
            disabled={running}
            className="rounded-xl bg-gold px-6 py-3 font-semibold text-navy-900 shadow-glow transition hover:brightness-110 disabled:opacity-50"
          >
            {running ? "Running…" : "Run rank.py →"}
          </button>
        </div>

        {meta && (
          <div className="mt-4 space-y-1 rounded-lg border border-glass-border bg-navy-900 p-3 font-mono text-xs text-ink-mute">
            <div>
              <span className="text-cyan">cmd</span> {meta.cmd}
            </div>
            <div>
              <span className="text-cyan">network</span> {meta.network}
            </div>
          </div>
        )}
      </div>

      {(lines.length > 0 || running) && (
        <div className="glass rounded-2xl p-6 shadow-glass">
          <h3 className="mb-3 font-mono text-xs uppercase tracking-wider text-ink-mute">
            Live log
          </h3>
          <div
            ref={logRef}
            role="log"
            aria-live="polite"
            className="max-h-72 overflow-y-auto rounded-lg border border-glass-border bg-black/40 p-4 font-mono text-xs leading-relaxed text-ink"
          >
            {lines.map((l, i) => (
              <div key={i} className={l.startsWith("[stderr]") ? "text-trap" : ""}>
                {l}
              </div>
            ))}
            {running && <div className="animate-pulse text-cyan">▌</div>}
          </div>
        </div>
      )}

      {result && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="glass rounded-2xl p-6 shadow-glass">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-mono text-xs uppercase tracking-wider text-ink-mute">
                submission.csv
              </h3>
              <span className="font-mono text-xs text-gold">
                {(result.wallMs / 1000).toFixed(2)}s · exit {result.exitCode}
              </span>
            </div>
            <pre className="max-h-72 overflow-auto rounded-lg border border-glass-border bg-black/40 p-4 font-mono text-[11px] text-ink">
              {result.csv || "(no CSV produced)"}
            </pre>
          </div>
          <div className="glass rounded-2xl p-6 shadow-glass">
            <h3 className="mb-3 font-mono text-xs uppercase tracking-wider text-ink-mute">
              validate_submission.py
            </h3>
            <pre className="max-h-72 overflow-auto rounded-lg border border-glass-border bg-black/40 p-4 font-mono text-xs text-cyan">
              {result.validator}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
