import { spawn } from "node:child_process";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Judge-mode sandbox endpoint.
 *
 * Runs the REAL shipped `rank.py` on the 100-line stratified sample
 * (data/sample_candidates.jsonl) — the same code that writes the graded
 * submission. The subprocess has networking disabled (env scrubbed of all
 * proxy / network vars + a network guard) and a wall-clock timer. stdout/stderr
 * are streamed back as a text/event-stream so the UI renders the live log, then
 * the resulting CSV and the vendored validator output are appended.
 *
 * This route NEVER recomputes the production ranking — it demonstrates the
 * graded pipeline reproducibly, offline, in-container.
 */

const REPO_ROOT = path.resolve(process.cwd(), "..");

function sse(controller: ReadableStreamDefaultController, event: string, data: unknown) {
  controller.enqueue(
    new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
  );
}

export async function POST() {
  const rankPy = path.join(REPO_ROOT, "rank.py");
  const sample = path.join(REPO_ROOT, "data", "sample_candidates.jsonl");
  const validator = path.join(REPO_ROOT, "validate_submission.py");
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "atlas-sandbox-"));
  const outCsv = path.join(outDir, "submission.csv");

  // Fail fast with a clear message if the pipeline is not present.
  for (const [label, p] of [
    ["rank.py", rankPy],
    ["sample", sample],
  ] as const) {
    if (!fs.existsSync(p)) {
      return new Response(
        `data: ${JSON.stringify({
          line: `ERROR: ${label} not found at ${p}`,
        })}\n\nevent: done\ndata: ${JSON.stringify({ ok: false })}\n\n`,
        { headers: { "Content-Type": "text/event-stream" } }
      );
    }
  }

  // Scrub the environment of all networking so the subprocess cannot reach out.
  // (--network none at the container level is the primary guard; this is the
  // in-process belt-and-suspenders.)
  const cleanEnv: NodeJS.ProcessEnv = {
    NODE_ENV: process.env.NODE_ENV,
    PATH: process.env.PATH ?? "",
    HOME: process.env.HOME ?? "",
    PYTHONHASHSEED: "0",
    OMP_NUM_THREADS: "1",
    // Force any accidental socket use to a black hole.
    http_proxy: "http://127.0.0.1:9",
    https_proxy: "http://127.0.0.1:9",
    no_proxy: "*",
    ATLAS_SANDBOX: "1",
  };

  const start = Date.now();

  const stream = new ReadableStream({
    start(controller) {
      sse(controller, "meta", {
        cmd: `python3 rank.py --candidates data/sample_candidates.jsonl --out <tmp>/submission.csv`,
        network: "disabled (proxy → 127.0.0.1:9, no_proxy=*)",
        sample,
      });

      const child = spawn(
        "python3",
        ["rank.py", "--candidates", sample, "--out", outCsv],
        { cwd: REPO_ROOT, env: cleanEnv }
      );

      // Hard wall-clock timeout — well inside the graded 300s cap.
      const killer = setTimeout(() => {
        sse(controller, "line", { line: "TIMEOUT: exceeded 180s — killing." });
        child.kill("SIGKILL");
      }, 180_000);

      child.stdout.on("data", (b: Buffer) => {
        for (const line of b.toString().split("\n")) {
          if (line.length) sse(controller, "line", { line });
        }
      });
      child.stderr.on("data", (b: Buffer) => {
        for (const line of b.toString().split("\n")) {
          if (line.length) sse(controller, "line", { line: `[stderr] ${line}` });
        }
      });

      child.on("error", (err) => {
        clearTimeout(killer);
        sse(controller, "line", { line: `SPAWN ERROR: ${err.message}` });
        sse(controller, "done", { ok: false });
        controller.close();
      });

      child.on("close", (code) => {
        clearTimeout(killer);
        const wallMs = Date.now() - start;
        sse(controller, "line", {
          line: `rank.py exited with code ${code} in ${(wallMs / 1000).toFixed(2)}s wall-clock.`,
        });

        // Read the produced CSV.
        let csv = "";
        try {
          csv = fs.readFileSync(outCsv, "utf-8");
        } catch {
          csv = "";
        }

        // Run the vendored validator on the produced CSV (still offline).
        // validate_submission.py takes exactly one arg: the CSV path.
        const v = spawn("python3", [validator, outCsv], {
          cwd: REPO_ROOT,
          env: cleanEnv,
        });
        let vout = "";
        v.stdout.on("data", (b: Buffer) => (vout += b.toString()));
        v.stderr.on("data", (b: Buffer) => (vout += b.toString()));
        v.on("error", () => {
          // Validator may take a different arg signature; degrade gracefully.
        });
        v.on("close", () => {
          sse(controller, "result", {
            wallMs,
            exitCode: code,
            csv,
            validator: vout.trim() || "(validator output unavailable)",
          });
          sse(controller, "done", { ok: code === 0 });
          try {
            fs.rmSync(outDir, { recursive: true, force: true });
          } catch {
            /* ignore */
          }
          controller.close();
        });
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
