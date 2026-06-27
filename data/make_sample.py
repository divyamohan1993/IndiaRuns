#!/usr/bin/env python3
"""Build data/sample_candidates.jsonl = 100 REAL lines stratified from the full pool.

Strata (deterministic, reproducible):
  - genuine AI-eng fits (probe example ids + AI-titled at product companies)
  - keyword-stuffer traps (non-eng title + AI skills)
  - structural honeypots (from the clean exclude set)
  - typical non-fits (random, seeded)

The sample exercises every code path (fit, trap, honeypot, sentinel) on 100 candidates.
Requires the full pool; point --source at it (default: ./candidates.jsonl).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core.io_jsonl import iter_candidates, write_jsonl  # noqa: E402

# Probe-identified example ids (data_probe.md §D).
GENUINE_FITS = [
    "CAND_0000165", "CAND_0000200", "CAND_0000422", "CAND_0000666", "CAND_0000981",
]
KEYWORD_STUFFERS = [
    "CAND_0000097", "CAND_0000121", "CAND_0000201",
]
# CAND_0000031 is an AI-TITLED structural honeypot (great catch). Pull from clean set too.
STRUCTURAL_HONEYPOTS_SEED = ["CAND_0000031"]

NON_ENG_TITLE_HINTS = (
    "marketing", "hr ", "human resource", "recruit", "sales", "content writer",
    "accountant", "operations", "customer support", "graphic designer",
    "project manager", "business analyst", "mechanical", "civil",
)
AI_SKILL_HINTS = (
    "llm", "embedding", "retrieval", "ranking", "rag", "vector", "pytorch",
    "tensorflow", "nlp", "transformer", "recommendation", "search", "fine-tuning",
)


def _has_ai_skill(c: dict) -> bool:
    txt = " ".join((s.get("name", "") or "").lower() for s in c.get("skills", []))
    return any(k in txt for k in AI_SKILL_HINTS)


def _is_non_eng(c: dict) -> bool:
    t = (c.get("profile", {}).get("current_title", "") or "").lower()
    return any(k in t for k in NON_ENG_TITLE_HINTS)


def load_clean_exclude(path: str | None) -> list[str]:
    if path and os.path.exists(path):
        d = json.load(open(path))
        ids = d if isinstance(d, list) else d.get("clean_exclude") or d.get("ids") or []
        return list(ids)
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--out", default=os.path.join(REPO, "data", "sample_candidates.jsonl"))
    ap.add_argument("--clean-exclude", default=None,
                    help="optional honeypot clean-exclude json (list of ids) to seed the honeypot stratum")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not os.path.exists(args.source):
        print(f"source pool not found: {args.source}\n"
              f"Run data/prepare_data.py first.", file=sys.stderr)
        return 1

    honeypot_ids = list(dict.fromkeys(STRUCTURAL_HONEYPOTS_SEED + load_clean_exclude(args.clean_exclude)))

    want_ids = set(GENUINE_FITS + KEYWORD_STUFFERS + honeypot_ids[:6])
    picked: dict[str, dict] = {}
    stuffer_pool: list[dict] = []
    honeypot_pool: list[dict] = []
    typical_pool: list[dict] = []
    honeypot_set = set(honeypot_ids)

    rng = random.Random(args.seed)
    for c in iter_candidates(args.source):
        cid = c.get("candidate_id")
        if cid in want_ids:
            picked[cid] = c
        elif cid in honeypot_set and len(honeypot_pool) < 60:
            honeypot_pool.append(c)
        elif _is_non_eng(c) and _has_ai_skill(c) and len(stuffer_pool) < 200:
            stuffer_pool.append(c)
        elif rng.random() < 0.02 and len(typical_pool) < 400:
            typical_pool.append(c)

    out: list[dict] = list(picked.values())
    rng.shuffle(stuffer_pool)
    rng.shuffle(honeypot_pool)
    rng.shuffle(typical_pool)

    def take(pool: list[dict], k: int) -> None:
        for c in pool:
            if len(out) >= args.n:
                break
            if c["candidate_id"] not in {x["candidate_id"] for x in out}:
                out.append(c)
            if sum(1 for _ in pool[: pool.index(c) + 1]) >= k:
                break

    # quotas: ~10 honeypots, ~25 stuffers, rest typical
    for c in honeypot_pool[:10]:
        if len(out) < args.n and c["candidate_id"] not in {x["candidate_id"] for x in out}:
            out.append(c)
    for c in stuffer_pool[:25]:
        if len(out) < args.n and c["candidate_id"] not in {x["candidate_id"] for x in out}:
            out.append(c)
    for c in typical_pool:
        if len(out) >= args.n:
            break
        if c["candidate_id"] not in {x["candidate_id"] for x in out}:
            out.append(c)

    out = out[: args.n]
    # sort by candidate_id for stable, reviewable output
    out.sort(key=lambda c: c["candidate_id"])
    n = write_jsonl(args.out, out)
    print(f"wrote {n} candidates -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
