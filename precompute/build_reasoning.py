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
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import reasoning as rsn  # noqa: E402
from core.artifacts import load_json, manifest_add  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from precompute.llm_rerank import _llm_target_ids, fact_bundle  # noqa: E402
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
    ap.add_argument("--top", type=int, default=0,
                    help="LLM-write reasoning only for the top-N shortlisted by first_pass; "
                         "the rest get deterministic reasoning. 0 = whole shortlist.")
    ap.add_argument("--concurrency", type=int, default=6,
                    help="parallel LLM calls (the claude -p CLI has high per-call latency).")
    args = ap.parse_args()
    A = args.artifacts_dir

    sl = load_json(os.path.join(A, "shortlist.json"), default={})
    shortlist = set(sl.get("ids", []))
    llm_targets = _llm_target_ids(A, sl, shortlist, args.top)
    backend = get_chat_backend(args.backend)
    bname = backend_name(backend)
    deterministic = bname == "DeterministicClient"
    print(f"reasoning backend: {bname} | shortlist={len(shortlist)} "
          f"| llm_targets={len(llm_targets)}")

    # phase 1: collect candidates (in stream order) and the subset that gets an LLM call
    ordered: list = []          # all shortlisted candidates, stream order
    call_items: list = []       # (cid, prompt) for the targeted subset
    for c in iter_candidates(args.candidates):
        cid = c["candidate_id"]
        if cid not in shortlist:
            continue
        ordered.append(c)
        if not deterministic and cid in llm_targets:
            call_items.append((cid, c))
    if args.max_calls:
        call_items = call_items[: args.max_calls]

    # phase 2: run the LLM calls concurrently, fact-validate each, keep only valid lines
    llm_text: dict = {}
    if call_items:
        print(f"LLM reasoning calls: {len(call_items)} @ concurrency={args.concurrency}")

        def _one(item):
            cid, c = item
            ans = backend.chat_json(SYSTEM, json.dumps(fact_bundle(c), ensure_ascii=False))
            cand_text = str(ans.get("reasoning", "")) if isinstance(ans, dict) else ""
            if cand_text and rsn._validate_llm(cand_text, c):
                return cid, rsn._csv_safe(cand_text)
            return cid, ""

        done = 0
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
            for cid, text in ex.map(_one, call_items):
                if text:
                    llm_text[cid] = text
                done += 1
                if done % 25 == 0:
                    print(f"  {done}/{len(call_items)} reasoning calls done")

    n_llm = len(llm_text)
    calls = len(call_items)
    with open(out_path := os.path.join(A, "reasoning.jsonl"), "w", encoding="utf-8") as out:
        for c in ordered:
            cid = c["candidate_id"]
            text = llm_text.get(cid) or rsn.deterministic_reasoning(c)
            out.write(json.dumps({"candidate_id": cid, "reasoning": text}, ensure_ascii=False) + "\n")

    manifest_add("reasoning", out_path, "precompute/build_reasoning.py", A,
                 extra={"backend": bname, "n_llm": n_llm})
    print(f"wrote {out_path} | llm_written={n_llm} calls={calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
