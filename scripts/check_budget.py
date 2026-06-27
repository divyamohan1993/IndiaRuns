#!/usr/bin/env python3
"""Fail if rank.py exceeds the budget: >=300s wall-clock or >=16 GiB peak RSS.

Runs rank.py as a subprocess with /usr/bin/time -v if available, else uses resource.
Usage: python scripts/check_budget.py --candidates ./candidates.jsonl --artifacts ./artifacts
"""

from __future__ import annotations

import argparse
import os
import resource
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TIME_LIMIT_S = 300
RSS_LIMIT_KB = 16 * 1024 * 1024  # 16 GiB in KiB


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--out", default=os.path.join(REPO, "submission.csv"))
    args = ap.parse_args()

    env = dict(os.environ, OMP_NUM_THREADS="1", PYTHONHASHSEED="0")
    cmd = [sys.executable, os.path.join(REPO, "rank.py"),
           "--candidates", args.candidates, "--out", args.out, "--artifacts", args.artifacts]
    t0 = time.time()
    res = subprocess.run(cmd, env=env)
    dt = time.time() - t0
    rss_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

    print(f"wall_clock={dt:.1f}s peak_child_rss={rss_kb/1024:.0f}MiB rc={res.returncode}")
    ok = True
    if res.returncode != 0:
        print("FAIL: rank.py non-zero exit"); ok = False
    if dt >= TIME_LIMIT_S:
        print(f"FAIL: exceeded {TIME_LIMIT_S}s"); ok = False
    if rss_kb >= RSS_LIMIT_KB:
        print(f"FAIL: exceeded 16 GiB"); ok = False
    if ok:
        print("OK: within budget.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
