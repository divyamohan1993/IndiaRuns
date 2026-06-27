#!/usr/bin/env python3
"""Fetch / symlink the 465 MB candidates.jsonl into the repo (gitignored).

The pool is never committed. This script makes `./candidates.jsonl` available from a
local path or URL so `rank.py` and the precompute scripts can find it.

Usage:
  python data/prepare_data.py --source /abs/path/to/candidates.jsonl   # symlink (default)
  python data/prepare_data.py --source /abs/path/to/candidates.jsonl --copy
  python data/prepare_data.py --source https://host/candidates.jsonl   # download
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import urllib.request

DEFAULT_DEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "candidates.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="local path or http(s) URL to candidates.jsonl")
    ap.add_argument("--dest", default=DEFAULT_DEST, help="destination path (default: repo-root/candidates.jsonl)")
    ap.add_argument("--copy", action="store_true", help="copy instead of symlink (local source only)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing dest")
    args = ap.parse_args()

    dest = os.path.abspath(args.dest)
    if os.path.exists(dest) or os.path.islink(dest):
        if not args.force:
            print(f"dest already exists: {dest} (use --force to overwrite)")
            return 0
        os.remove(dest)

    src = args.source
    if src.startswith("http://") or src.startswith("https://"):
        print(f"downloading {src} -> {dest} ...")
        urllib.request.urlretrieve(src, dest)  # noqa: S310 — operator-supplied URL, Plane A only
    else:
        src = os.path.abspath(src)
        if not os.path.exists(src):
            print(f"source not found: {src}", file=sys.stderr)
            return 1
        if args.copy:
            print(f"copying {src} -> {dest} ...")
            shutil.copy2(src, dest)
        else:
            print(f"symlinking {src} -> {dest}")
            os.symlink(src, dest)

    size = os.path.getsize(dest)
    print(f"ready: {dest} ({size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
