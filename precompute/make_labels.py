#!/usr/bin/env python3
"""Build proxy_tiers.npy (tier 0-5) over the pool from the JD-encoded rule proxy.

INTERNAL relevance proxy only (NDCG estimation + LTR labels) — never a ground truth.
Two-pass for the company-age honeypot proxy. Also writes a tier histogram for docs.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core import rule_fit  # noqa: E402
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
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    args = ap.parse_args()
    os.makedirs(args.artifacts_dir, exist_ok=True)

    cf = build_company_first(args.candidates)
    tiers = []
    hist = collections.Counter()
    for c in iter_candidates(args.candidates):
        t, _ = rule_fit.proxy_tier(c, company_first=cf)
        tiers.append(t)
        hist[t] += 1

    arr = np.asarray(tiers, dtype=np.int8)
    np.save(os.path.join(args.artifacts_dir, "proxy_tiers.npy"), arr)
    save_json(os.path.join(args.artifacts_dir, "proxy_tier_hist.json"),
              {str(k): hist[k] for k in range(6)})
    manifest_add("proxy_tiers", os.path.join(args.artifacts_dir, "proxy_tiers.npy"),
                 "precompute/make_labels.py", args.artifacts_dir, extra={"hist": {str(k): hist[k] for k in range(6)}})

    print("tier histogram:", {k: hist[k] for k in range(6)})
    print(f"wrote proxy_tiers.npy ({arr.shape})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
