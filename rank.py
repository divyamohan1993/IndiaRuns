#!/usr/bin/env python3
"""Plane B graded ranker — CPU-only, no network, <=5 min, <=16 GB.

Loads frozen artifacts, streams candidates.jsonl, re-derives live signals with the SHARED
features.py, fuses the sub-scores into a margin (LTR if calibration says so, else the
fixed-weight blend), applies anti-trap caps + behavioral multiplier + the honeypot gate,
selects the top-100 with id-ascending tie-break, attaches frozen (re-validated) reasoning,
self-validates with the vendored validator, then writes submission.csv.

Usage:
  python rank.py --candidates ./candidates.jsonl --out ./submission.csv [--mode fast|self-contained]

--mode fast (default): reads frozen per-candidate embeddings (cand_emb) — no model load.
--mode self-contained: re-derives the dense signal from the pre-fit TF-IDF/SVD pickle
  (sklearn .transform, ~24s/100K) instead of trusting frozen embeddings — an audit path.
"""

from __future__ import annotations

import argparse
import os
import sys

# Determinism: set BEFORE numpy import so BLAS honors single-thread.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("PYTHONHASHSEED", "0")

import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

import features as feat  # noqa: E402
import reasoning as rsn  # noqa: E402
from core import gbdt, subscores  # noqa: E402
from core import rule_fit as rf  # noqa: E402
from core import score as scoremod
from core.artifacts import load_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from core.schema import parse_date  # noqa: E402


def _load_reasoning(artifacts_dir: str) -> dict:
    path = os.path.join(artifacts_dir, "reasoning.jsonl")
    out = {}
    if os.path.exists(path):
        import json
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                out[r["candidate_id"]] = r.get("reasoning", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--out", default=os.path.join(REPO, "submission.csv"))
    ap.add_argument("--artifacts", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--mode", choices=["fast", "self-contained"], default="fast")
    args = ap.parse_args()
    A = args.artifacts

    # ---- load frozen artifacts ----
    idx = load_json(os.path.join(A, "candidate_index.json"))
    if not idx:
        sample_art = os.path.join(REPO, "artifacts_sample")
        print(
            f"missing candidate_index.json (and the frozen arrays) in {A}.\n"
            "The full-pool artifacts (candidate_index.json + the large *.npy/*.npz binaries)\n"
            "are regenerable and not committed. To reproduce:\n"
            f"  - quick out-of-the-box demo on the shipped 100-line sample:\n"
            f"      python rank.py --candidates data/sample_candidates.jsonl "
            f"--out submission.csv --artifacts {sample_art}\n"
            "  - full pool: regenerate Plane-A artifacts first, then re-run:\n"
            "      python precompute/run_all.py --candidates ./candidates.jsonl "
            "--artifacts ./artifacts",
            file=sys.stderr,
        )
        return 2
    ids = idx["ids"]
    det_names = idx["det_feature_names"]
    id_to_row = {cid: i for i, cid in enumerate(ids)}

    cand_emb = np.load(os.path.join(A, "cand_emb.f16.npy"), mmap_mode="r")
    jz = np.load(os.path.join(A, "jd_clause_emb.npz"))
    bm25 = np.load(os.path.join(A, "bm25.npz"))["bm25"].astype(np.float32)
    lex = np.load(os.path.join(A, "lexical_cos_jd.f16.npy")).astype(np.float32)

    # self-contained dense recompute (audit): use the pre-fit vectorizer
    if args.mode == "self-contained":
        try:
            import pickle
            with open(os.path.join(A, "tfidf_svd.pkl"), "rb") as f:
                blob = pickle.load(f)
            narr = [feat.narrative_text(c) for c in iter_candidates(args.candidates)]
            Z = blob["svd"].transform(blob["vectorizer"].transform(narr)).astype(np.float32)
            dim = cand_emb.shape[1]
            if Z.shape[1] < dim:
                Zp = np.zeros((Z.shape[0], dim), dtype=np.float32)
                Zp[:, : Z.shape[1]] = Z
                Z = Zp
            norms = np.linalg.norm(Z, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            cand_emb = Z / norms
        except Exception as e:  # noqa: BLE001
            print(f"self-contained recompute failed ({e}); using frozen embeddings", file=sys.stderr)

    cand_emb = np.asarray(cand_emb, dtype=np.float32)
    S_dense = subscores.dense_scores(cand_emb, jz["clauses"], jz["weights"], jz["ideal"])

    calib = load_json(os.path.join(A, "calibration.json"), default={"use_ltr": False})
    use_ltr = bool(calib.get("use_ltr"))
    booster = gbdt.FrozenGBDT.load(os.path.join(A, "ltr_trees.npz")) if use_ltr else None
    ltr_model = load_json(os.path.join(A, "ltr_model.json"), default={})
    ltr_feature_order = ltr_model.get("feature_order", [])

    llm_scores = load_json(os.path.join(A, "llm_scores.json"), default={}) or {}
    frozen_hp_payload = load_json(os.path.join(A, "honeypot_excludes.json"), default={})
    frozen_exclude = set(frozen_hp_payload.get("clean_exclude", [])
                         if isinstance(frozen_hp_payload, dict) else frozen_hp_payload or [])
    frozen_reasoning = _load_reasoning(A)

    # ---- pass 1: company_first for the honeypot company-age proxy ----
    company_first = {}
    for c in iter_candidates(args.candidates):
        for j in c.get("career_history", []) or []:
            if not isinstance(j, dict):
                continue
            comp = (j.get("company") or "").strip().lower()
            sd = parse_date(j.get("start_date"))
            if comp and sd and (comp not in company_first or sd < company_first[comp]):
                company_first[comp] = sd

    # ---- pass 2: stream, re-derive features + rule, assemble margin ----
    cids: list[str] = []
    dets: list[dict] = []
    cands: list[dict] = []
    S_rule = []
    S_llm = []
    rows_emb = []
    for c in iter_candidates(args.candidates):
        cid = c["candidate_id"]
        r = id_to_row.get(cid)
        det = feat.extract_det(c, company_first=company_first)
        cids.append(cid)
        dets.append(det)
        cands.append(c)
        S_rule.append(rf.rule_fit(c, company_first=company_first))
        ls = llm_scores.get(cid)
        S_llm.append(float(ls.get("fit_score", 0)) / 100.0 if isinstance(ls, dict) else 0.0)
        rows_emb.append(r if r is not None else -1)

    m = len(cids)
    S_rule = np.asarray(S_rule, dtype=np.float32)
    S_llm = np.asarray(S_llm, dtype=np.float32)
    # align frozen per-row arrays to streamed order
    rows_emb = np.asarray(rows_emb)
    valid = rows_emb >= 0
    S_dense_aligned = np.zeros(m, dtype=np.float32)
    S_bm25_aligned = np.zeros(m, dtype=np.float32)
    lex_aligned = np.zeros(m, dtype=np.float32)
    S_dense_aligned[valid] = S_dense[rows_emb[valid]]
    S_bm25_aligned[valid] = bm25[rows_emb[valid]]
    lex_aligned[valid] = lex[rows_emb[valid]]

    has_llm = S_llm > 0
    base_sl = subscores.base_fit_shortlisted(S_llm, S_dense_aligned, S_rule, S_bm25_aligned)
    base_lt = subscores.base_fit_longtail(S_rule, S_dense_aligned, S_bm25_aligned)
    base_fit = np.where(has_llm, base_sl, base_lt).astype(np.float32)

    if booster is not None and ltr_feature_order:
        # assemble the LTR matrix in the frozen feature order
        det_mat = np.array([[d.get(nm, 0.0) for nm in det_names] for d in dets], dtype=np.float32)
        extra = {
            "S_dense": S_dense_aligned, "S_bm25": S_bm25_aligned, "S_rule": S_rule,
            "S_llm": S_llm,
            "behavioral_composite": np.array([d.get("availability_composite", 0.5) for d in dets], dtype=np.float32),
            "emb_cos_jd_overall": subscores.role_title_cos(cand_emb, jz["ideal"])[rows_emb.clip(min=0)] * valid,
            "lexical_cos_jd": lex_aligned,
        }
        cols = []
        for nm in ltr_feature_order:
            if nm in det_names:
                cols.append(det_mat[:, det_names.index(nm)])
            elif nm in extra:
                cols.append(extra[nm])
            else:
                cols.append(np.zeros(m, dtype=np.float32))
        X = np.column_stack(cols).astype(np.float32)
        margin = booster.predict(X).astype(np.float64)
    else:
        margin = base_fit.astype(np.float64)

    # ---- gate + behavioral + caps ----
    final, _ = scoremod.assemble_final(cids, margin, dets, cands, frozen_exclude, company_first)
    chosen = scoremod.select_top100_with_paranoia(cids, final, dets, cands, frozen_exclude, company_first)

    if len(chosen) < 100:
        print(f"WARNING: only {len(chosen)} candidates survived the gate "
              f"(pool has {m}); submission needs 100.", file=sys.stderr)

    def reason_for(i: int) -> str:
        cid = cids[i]
        cached = frozen_reasoning.get(cid)
        return rsn.build_reasoning(cands[i], {"llm_reasoning": cached} if cached else None)

    rows = scoremod.to_rows(cids, final, chosen, reason_for)
    scoremod.write_csv(args.out, rows)

    errors = scoremod.preflight_validate(args.out)
    if errors:
        print("SELF-VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        return 1
    print(f"wrote {args.out} ({len(rows)} rows) — self-validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
