import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * AI backend status. The spine is fully functional offline ("deterministic
 * brain"); live generation routes only light up if a key is present in the
 * server env. The status pill reads this and renders honestly (Live ● /
 * Offline ○). We never expose the key value to the client — only the boolean.
 */
export function aiBackendLive(): boolean {
  return Boolean(
    process.env.NVIDIA_API_KEY ||
      process.env.ATLAS_AI_LIVE === "1" ||
      process.env.CLAUDE_CLI_AVAILABLE === "1"
  );
}
