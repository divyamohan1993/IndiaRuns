"""LLM + embedding backends for Plane A, selected by env.

Backends (LLM_BACKEND, else auto):
  - nvidia        : OpenAI-compatible NVIDIA NIM (NVIDIA_API_KEY). Chat + embeddings.
  - claude_cli    : shells out to the local `claude -p` CLI (no API key needed here).
  - deterministic : no network; returns a rule-derived JSON (always available).

All chat backends expose chat_json(system, user) -> dict and the NVIDIA backend also
exposes embed(texts, input_type). Plane B NEVER imports this module.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from typing import List, Optional


def _strip_json(text: str) -> Optional[dict]:
    text = text.strip()
    # tolerate code fences / prose around a JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- NVIDIA
class NvidiaClient:
    request_count = 0  # process-wide successful-POST counter (for offline reporting)

    def __init__(self):
        self.api_key = os.environ.get("NVIDIA_API_KEY", "")
        self.base = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
        # NVIDIA_CHAT_MODEL is authoritative; NVIDIA_MODEL is an accepted alias.
        self.chat_model = (os.environ.get("NVIDIA_CHAT_MODEL")
                           or os.environ.get("NVIDIA_MODEL")
                           or "meta/llama-3.3-70b-instruct")
        self.embed_model = os.environ.get("NVIDIA_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
        # per-call timeout; >=60s so an occasional cold-start spike (24-40s seen on
        # llama-3.3-70b) does not get treated as a failure. Override via NVIDIA_TIMEOUT.
        self.timeout = float(os.environ.get("NVIDIA_TIMEOUT", "90"))
        self.max_tokens = int(os.environ.get("NVIDIA_MAX_TOKENS", "600"))

    def available(self) -> bool:
        return bool(self.api_key)

    def _post(self, path: str, payload: dict, retries: int = 6, timeout: float = None) -> dict:
        import httpx  # imported lazily; Plane A only
        url = f"{self.base}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        to = self.timeout if timeout is None else timeout
        delay = 1.0
        last = None
        for _ in range(retries):
            try:
                r = httpx.post(url, headers=headers, json=payload, timeout=to)
                if r.status_code in (429, 500, 502, 503, 504):
                    last = RuntimeError(f"{r.status_code}: {r.text[:200]}")
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                r.raise_for_status()
                NvidiaClient.request_count += 1
                return r.json()
            except Exception as e:  # noqa: BLE001  (timeouts / transport errors -> backoff+retry)
                last = e
                time.sleep(delay)
                delay = min(delay * 2, 30)
        raise RuntimeError(f"NVIDIA request failed after retries: {last}")

    def chat_json(self, system: str, user: str) -> dict:
        out = self._post("/chat/completions", {
            "model": self.chat_model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        content = out["choices"][0]["message"]["content"]
        return _strip_json(content) or {}

    def embed(self, texts: List[str], input_type: str = "passage",
              truncate: str = "END") -> List[List[float]]:
        out = self._post("/embeddings", {
            "model": self.embed_model,
            "input": texts,
            "input_type": input_type,
            "encoding_format": "float",
            "truncate": truncate,
        })
        # NVIDIA returns data possibly out of order; sort by index to be safe.
        data = sorted(out["data"], key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in data]


# ------------------------------------------------------------------------- claude CLI
class ClaudeCliClient:
    def __init__(self):
        self.bin = shutil.which("claude")

    def available(self) -> bool:
        return bool(self.bin)

    def chat_json(self, system: str, user: str) -> dict:
        prompt = (f"{system}\n\n{user}\n\n"
                  "Respond with ONLY a single JSON object, no prose, no code fences.")
        try:
            res = subprocess.run([self.bin, "-p", prompt], capture_output=True, text=True, timeout=120)
        except Exception:
            return {}
        return _strip_json(res.stdout) or {}


# ----------------------------------------------------------------------- deterministic
class DeterministicClient:
    """No network. The LLM step degrades to this; the rule proxy already supplies a tier."""

    def available(self) -> bool:
        return True

    def chat_json(self, system: str, user: str) -> dict:
        return {}  # caller falls back to rule-derived fit


def get_chat_backend(name: Optional[str] = None):
    name = (name or os.environ.get("LLM_BACKEND") or "auto").lower()
    if name == "nvidia":
        c = NvidiaClient()
        return c if c.available() else DeterministicClient()
    if name == "claude_cli":
        c = ClaudeCliClient()
        return c if c.available() else DeterministicClient()
    if name == "deterministic":
        return DeterministicClient()
    # auto
    nv = NvidiaClient()
    if nv.available():
        return nv
    cli = ClaudeCliClient()
    if cli.available():
        return cli
    return DeterministicClient()


def backend_name(backend) -> str:
    return type(backend).__name__
