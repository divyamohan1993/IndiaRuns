#!/usr/bin/env python3
"""Regenerate honeypot_excludes.json = the CLEAN structural-impossibility union.

This DOES NOT read ge1/ge2 from any external artifact. It recomputes the clean union
from scratch using core.honeypot.clean_signatures over the pool (two passes: pass 1
learns earliest-start-per-company for the company-age proxy; pass 2 flags).

On the full 100K pool this yields exactly 201 candidate_ids. On the 100-line sample it
yields a small set (whatever clean signatures the sample candidates trip). The two noisy
signatures (skill_duration_exceeds_career, edu_degree_order_impossible) are deliberately
DEMOTED and never enter this set.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core import honeypot  # noqa: E402
from core.artifacts import manifest_add, save_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from core.schema import parse_date  # noqa: E402


def build_company_first(path: str) -> dict:
    cf = {}
    for c in iter_candidates(path):
        for j in c.get("career_history", []) or []:
            if not isinstance(j, dict):
                continue
            comp = (j.get("company") or "").strip().lower()
            sd = parse_date(j.get("start_date"))
            if comp and sd and (comp not in cf or sd < cf[comp]):
                cf[comp] = sd
    return cf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--out", default=os.path.join(REPO, "artifacts", "honeypot_excludes.json"))
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    args = ap.parse_args()

    if not os.path.exists(args.candidates):
        print(f"pool not found: {args.candidates}", file=sys.stderr)
        return 1

    print("pass 1: learning earliest-start-per-company ...")
    cf = build_company_first(args.candidates)

    print("pass 2: flagging clean structural impossibilities ...")
    excl = []
    sig_counts = collections.Counter()
    soft_counts = collections.Counter()
    total = 0
    for c in iter_candidates(args.candidates):
        total += 1
        sigs = honeypot.clean_signatures(c, company_first=cf)
        if sigs:
            excl.append(c["candidate_id"])
            for s in sigs:
                sig_counts[s] += 1
        for s in honeypot.soft_signatures(c):
            soft_counts[s] += 1

    excl = sorted(set(excl))
    payload = {
        "clean_exclude": excl,
        "count": len(excl),
        "signature_counts": dict(sig_counts),
        "soft_signature_counts_demoted": dict(soft_counts),
        "total_scanned": total,
        "note": "Clean structural-impossibility union ONLY. Salary inversion is the "
                "dataset norm and is NEVER included. The two soft signatures are demoted.",
    }
    save_json(args.out, payload)
    manifest_add("honeypot_excludes", args.out, producer="precompute/build_honeypots.py",
                 artifacts_dir=args.artifacts_dir)

    print(f"scanned {total} | clean exclude = {len(excl)}")
    for k, v in sig_counts.most_common():
        print(f"  {v:6d}  {k}")
    print("  -- demoted to soft (NOT excluded) --")
    for k, v in soft_counts.most_common():
        print(f"  {v:6d}  {k}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
