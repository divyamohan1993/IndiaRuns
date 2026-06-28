import { spawn } from "node:child_process";

/**
 * Backend selector for the live AI routes (Plane C only — NEVER on the graded
 * rank.py path). Resolution order, highest fidelity first:
 *
 *   1. NVIDIA hosted endpoint  (integrate.api.nvidia.com)  — when NVIDIA_API_KEY set
 *   2. local CLI LLM           ('claude -p')               — when CLAUDE_CLI_AVAILABLE=1
 *   3. deterministic template  (pure function, no network) — always available
 *
 * Every caller passes a deterministic `fallback()` so the product is fully
 * functional and visually identical with zero keys. The status pill reflects
 * which backend actually answered (see `backendName`). We never expose the key.
 */

export type BackendName = "nvidia" | "cli" | "offline";

export function backendName(): BackendName {
  if (process.env.NVIDIA_API_KEY) return "nvidia";
  if (process.env.CLAUDE_CLI_AVAILABLE === "1") return "cli";
  return "offline";
}

export type GenInput = {
  /** System framing — task + guardrails. */
  system: string;
  /** User content — the fact bundle the model must stay grounded in. */
  user: string;
  /** Deterministic, network-free answer. Always correct, always available. */
  fallback: () => string;
  /** Soft cap on output length (chars). */
  maxChars?: number;
  /** Per-call timeout (ms). */
  timeoutMs?: number;
};

export type GenResult = { text: string; backend: BackendName };

const NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions";
// Model id is read from env so no provider/model identifier is hard-coded here.
const NVIDIA_MODEL = process.env.NVIDIA_MODEL || "";

/** Generate text via the best available backend, degrading to the fallback. */
export async function generate(input: GenInput): Promise<GenResult> {
  const { system, user, fallback, maxChars = 600, timeoutMs = 12_000 } = input;

  // 1) NVIDIA hosted endpoint.
  if (process.env.NVIDIA_API_KEY && NVIDIA_MODEL) {
    try {
      const text = await nvidiaGenerate(system, user, maxChars, timeoutMs);
      if (text) return { text: clip(text, maxChars), backend: "nvidia" };
    } catch {
      /* fall through */
    }
  }

  // 2) Local CLI LLM.
  if (process.env.CLAUDE_CLI_AVAILABLE === "1") {
    try {
      const text = await cliGenerate(system, user, timeoutMs);
      if (text) return { text: clip(text, maxChars), backend: "cli" };
    } catch {
      /* fall through */
    }
  }

  // 3) Deterministic fallback.
  return { text: clip(fallback(), maxChars), backend: "offline" };
}

function clip(s: string, n: number): string {
  const t = s.trim();
  return t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t;
}

async function nvidiaGenerate(
  system: string,
  user: string,
  maxChars: number,
  timeoutMs: number
): Promise<string> {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(NVIDIA_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.NVIDIA_API_KEY}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        model: NVIDIA_MODEL,
        temperature: 0.2,
        max_tokens: Math.ceil(maxChars / 3) + 64,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
      signal: ctrl.signal,
    });
    if (!res.ok) return "";
    const json = (await res.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    return json.choices?.[0]?.message?.content?.trim() ?? "";
  } finally {
    clearTimeout(to);
  }
}

function cliGenerate(
  system: string,
  user: string,
  timeoutMs: number
): Promise<string> {
  return new Promise((resolve) => {
    // 'claude -p' reads the prompt from argv and prints the completion to stdout.
    const prompt = `${system}\n\n${user}`;
    const child = spawn("claude", ["-p", prompt], {
      env: { ...process.env },
    });
    let out = "";
    let done = false;
    const finish = (v: string) => {
      if (!done) {
        done = true;
        resolve(v);
      }
    };
    const killer = setTimeout(() => {
      child.kill("SIGKILL");
      finish("");
    }, timeoutMs);
    child.stdout.on("data", (b: Buffer) => (out += b.toString()));
    child.on("error", () => {
      clearTimeout(killer);
      finish("");
    });
    child.on("close", () => {
      clearTimeout(killer);
      finish(out.trim());
    });
  });
}
