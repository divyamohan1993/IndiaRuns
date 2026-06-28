#!/usr/bin/env python3
"""Run the full Plane-A pipeline in order to produce all frozen artifacts.

  build_features -> fit_lexical -> embed -> make_labels -> build_honeypots ->
  first_pass_shortlist -> llm_rerank -> train_ltr -> build_reasoning

--mode local : embed via TF-IDF/SVD fallback + deterministic LLM (no keys, fast).
--mode auto  : embed via best backend (NVIDIA/BGE) + best LLM backend.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(mod: str, *cli: str) -> None:
    cmd = [sys.executable, os.path.join(REPO, "precompute", mod), *cli]
    print("\n=== " + mod + " ===")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"{mod} failed (exit {r.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--mode", choices=["local", "auto"], default="local")
    ap.add_argument("--k", type=int, default=1200)
    args = ap.parse_args()
    C = ["--candidates", args.candidates]
    Ad = ["--artifacts-dir", args.artifacts]
    embed_backend = ["--backend", "svd"] if args.mode == "local" else ["--backend", "auto"]
    llm_backend = ["--backend", "deterministic"] if args.mode == "local" else ["--backend", "auto"]

    run("build_features.py", *C, *Ad)
    run("fit_lexical.py", *C, *Ad)
    run("embed.py", *C, *Ad, *embed_backend)
    run("make_labels.py", *C, *Ad)
    run("build_honeypots.py", *C, "--out", os.path.join(args.artifacts, "honeypot_excludes.json"), *Ad)
    run("first_pass_shortlist.py", *C, *Ad, "--k", str(args.k))
    run("llm_rerank.py", *C, *Ad, *llm_backend)
    run("train_ltr.py", *Ad)
    run("build_reasoning.py", *C, *Ad, *llm_backend)
    print("\nPlane A complete:", args.artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
