#!/usr/bin/env python3
"""Build reasoning.jsonl for the shortlist (~top picks), LLM-written + fact-validated.

For each shortlisted id: prompt the LLM with ONLY that candidate's parsed facts to write
a <=140-char comma-free fact-grounded reason. Post-validate offline with reasoning._validate_llm;
if it fails (or no LLM), store the deterministic reasoning. rank.py reads reasoning.jsonl and
re-validates per row at attach time, so a bad cached line can never reach the CSV.

Degrades to deterministic for every row when no LLM backend is available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import reasoning as rsn  # noqa: E402
from core.artifacts import load_json, manifest_add  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from precompute.llm_rerank import fact_bundle  # noqa: E402
from precompute.nvidia_client import backend_name, get_chat_backend  # noqa: E402

SYSTEM = (
    "Write a single recruiter-facing one-line reason (<=140 characters, NO commas) for why "
    "this candidate fits a Senior AI Engineer ranking/search role. Use ONLY the facts given; "
    "never invent skills, companies, or numbers. State one honest concern if a gap exists. "
    "Return ONLY JSON: {\"reasoning\": \"...\"}."
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--backend", default=None)
    ap.add_argument("--max-calls", type=int, default=0)
    args = ap.parse_args()
    A = args.artifacts_dir

    sl = load_json(os.path.join(A, "shortlist.json"), default={})
    shortlist = set(sl.get("ids", []))
    backend = get_chat_backend(args.backend)
    bname = backend_name(backend)
    deterministic = bname == "DeterministicClient"
    print(f"reasoning backend: {bname} | shortlist={len(shortlist)}")

    out_path = os.path.join(A, "reasoning.jsonl")
    calls = 0
    n_llm = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for c in iter_candidates(args.candidates):
            cid = c["candidate_id"]
            if cid not in shortlist:
                continue
            text = ""
            if not deterministic and not (args.max_calls and calls >= args.max_calls):
                ans = backend.chat_json(SYSTEM, json.dumps(fact_bundle(c), ensure_ascii=False))
                calls += 1
                cand_text = str(ans.get("reasoning", "")) if isinstance(ans, dict) else ""
                if cand_text and rsn._validate_llm(cand_text, c):
                    text = rsn._csv_safe(cand_text)
                    n_llm += 1
            if not text:
                text = rsn.deterministic_reasoning(c)
            out.write(json.dumps({"candidate_id": cid, "reasoning": text}, ensure_ascii=False) + "\n")

    manifest_add("reasoning", out_path, "precompute/build_reasoning.py", A,
                 extra={"backend": bname, "n_llm": n_llm})
    print(f"wrote {out_path} | llm_written={n_llm} calls={calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
