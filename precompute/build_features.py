#!/usr/bin/env python3
"""Build cand_features.f16.npy (N x N_DET) over the pool using the SHARED features.py.

Only the deterministic features (Groups A-E) are written here; Group F (semantic) is
appended at rank time from the frozen embeddings/lexical cosines. Also writes
candidate_index.json (row -> candidate_id) so rank.py can align frozen rows to streamed
records by id.

Two passes: pass 1 learns company_first for the company-age honeypot proxy; pass 2 extracts.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import features  # noqa: E402
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

    print("pass 1: company_first ...")
    cf = build_company_first(args.candidates)

    print("pass 2: deterministic features ...")
    rows = []
    ids = []
    det_names = features.DET_FEATURE_NAMES
    for i, c in enumerate(iter_candidates(args.candidates)):
        d = features.extract_det(c, company_first=cf)
        rows.append([d[n] for n in det_names])
        ids.append(c["candidate_id"])
        if (i + 1) % 20000 == 0:
            print(f"  {i+1} ...")

    mat = np.asarray(rows, dtype=np.float16)
    feat_path = os.path.join(args.artifacts_dir, "cand_features.f16.npy")
    np.save(feat_path, mat)
    idx_path = os.path.join(args.artifacts_dir, "candidate_index.json")
    save_json(idx_path, {"ids": ids, "n": len(ids), "det_feature_names": det_names})

    manifest_add("cand_features", feat_path, "precompute/build_features.py", args.artifacts_dir,
                 extra={"shape": list(mat.shape)})
    manifest_add("candidate_index", idx_path, "precompute/build_features.py", args.artifacts_dir)
    print(f"wrote {feat_path} {mat.shape} and {idx_path} ({len(ids)} ids)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
