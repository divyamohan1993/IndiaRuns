#!/usr/bin/env python3
"""Assert a submission CSV contains 0 honeypots in the top-100 (and top-10).

Cross-checks the ranked ids against (a) the frozen clean-exclude set and (b) a live
re-run of the clean structural checks over the candidate pool. Exits non-zero on any
honeypot in the top-100 — the CI gate.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core import honeypot  # noqa: E402
from core.artifacts import load_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--excludes", default=os.path.join(REPO, "artifacts", "honeypot_excludes.json"))
    args = ap.parse_args()

    with open(args.submission, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("candidate_id")]
    ranked = {r["candidate_id"]: int(r["rank"]) for r in rows}

    frozen = set()
    payload = load_json(args.excludes, default=None)
    if isinstance(payload, dict):
        frozen = set(payload.get("clean_exclude", []))
    elif isinstance(payload, list):
        frozen = set(payload)

    live_hp = set()
    if os.path.exists(args.candidates):
        wanted = set(ranked)
        for c in iter_candidates(args.candidates):
            if c.get("candidate_id") in wanted and honeypot.is_honeypot(c):
                live_hp.add(c["candidate_id"])

    bad = {cid: ranked[cid] for cid in ranked if cid in frozen or cid in live_hp}
    top10_bad = {cid: r for cid, r in bad.items() if r <= 10}

    print(f"ranked={len(ranked)} frozen_set={len(frozen)} honeypots_in_top100={len(bad)} in_top10={len(top10_bad)}")
    if bad:
        for cid, r in sorted(bad.items(), key=lambda x: x[1]):
            print(f"  HONEYPOT in top-100 at rank {r}: {cid}")
        return 1
    print("OK: 0 honeypots in top-100.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
