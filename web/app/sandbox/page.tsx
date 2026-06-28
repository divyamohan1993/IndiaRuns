import { SandboxClient } from "./sandbox-client";

export const metadata = {
  title: "Sandbox — ATLAS",
  description: "Run the real rank.py offline on a 100-candidate sample.",
};

export default function SandboxPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-cyan">
          Judge mode
        </p>
        <h1 className="mt-2 text-3xl font-bold text-ink">Sandbox</h1>
        <p className="mt-2 max-w-2xl text-ink-mute">
          The single inviolable rule: no network, GPU, or LLM ever sits on the
          graded rank-time path. This page proves it — it executes the shipped{" "}
          <code className="font-mono text-gold">rank.py</code> in-container with
          networking disabled and a wall-clock timer, then validates the output
          with the vendored contest validator.
        </p>
      </header>

      <SandboxClient />
    </div>
  );
}
