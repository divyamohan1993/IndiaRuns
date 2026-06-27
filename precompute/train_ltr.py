#!/usr/bin/env python3
"""Train a monotone-constrained XGBoost ranker and freeze it to numpy trees.

Feature vector = the deterministic features (Groups A-E from cand_features.f16.npy) +
the four sub-scores (dense, bm25, rule, llm) + behavioral composite + the semantic
Group-F cosines. Monotone signs come from features.MONOTONE.

Decision rule (spec §2.6): keep the LTR ONLY if it beats the fixed-weight base_fit blend
on 5-fold proxy CV-NDCG@10. Otherwise ship the blend (calibration.json records the choice).

Exports:
  - ltr_trees.npz   : flat arrays (node split feature/threshold/children/leaf values)
  - ltr_model.json  : metadata (feature order, n_trees, base_score, learning details)
  - calibration.json: {"use_ltr": bool, "blend_weights": {...}, "cv_ndcg": {...}}

Degrades gracefully: if xgboost is unavailable or LTR loses, use_ltr=False and the blend
ships. core/gbdt.py only evaluates ltr_trees.npz when use_ltr is True.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import features as feat  # noqa: E402
from core import subscores  # noqa: E402
from core.artifacts import load_json, manifest_add, save_json  # noqa: E402

# The LTR feature order: deterministic features then the engineered sub-scores.
EXTRA_FEATURES = ["S_dense", "S_bm25", "S_rule", "S_llm", "behavioral_composite",
                  "emb_cos_jd_overall", "lexical_cos_jd"]


def ndcg_at_k(rel: np.ndarray, scores: np.ndarray, k: int = 10) -> float:
    order = np.argsort(-scores, kind="mergesort")[:k]
    gains = (2.0 ** rel[order] - 1)
    discounts = 1.0 / np.log2(np.arange(2, 2 + len(order)))
    dcg = float(np.sum(gains * discounts))
    ideal = np.argsort(-rel, kind="mergesort")[:k]
    idcg = float(np.sum((2.0 ** rel[ideal] - 1) * (1.0 / np.log2(np.arange(2, 2 + len(ideal))))))
    return dcg / idcg if idcg > 0 else 0.0


def assemble_matrix(A: str):
    idx = load_json(os.path.join(A, "candidate_index.json"))
    ids = idx["ids"]
    n = len(ids)
    det = np.load(os.path.join(A, "cand_features.f16.npy")).astype(np.float32)
    det_names = idx["det_feature_names"]

    cand_emb = np.load(os.path.join(A, "cand_emb.f16.npy")).astype(np.float32)
    jz = np.load(os.path.join(A, "jd_clause_emb.npz"))
    S_dense = subscores.dense_scores(cand_emb, jz["clauses"], jz["weights"], jz["ideal"])
    S_bm25 = np.load(os.path.join(A, "bm25.npz"))["bm25"].astype(np.float32)
    lex = np.load(os.path.join(A, "lexical_cos_jd.f16.npy")).astype(np.float32)
    emb_jd = subscores.role_title_cos(cand_emb, jz["ideal"])  # proxy overall cos

    # S_rule + behavioral from the deterministic matrix columns
    col = {nm: det[:, i] for i, nm in enumerate(det_names)}
    S_rule = np.zeros(n, dtype=np.float32)  # rule is recomputed in labels; approximate via tier-free proxy
    # use availability_composite as behavioral
    behav = col.get("availability_composite", np.full(n, 0.5, dtype=np.float32))

    # llm scores (optional)
    S_llm = np.zeros(n, dtype=np.float32)
    llm = load_json(os.path.join(A, "llm_scores.json"), default=None)
    if isinstance(llm, dict):
        id_to_row = {cid: i for i, cid in enumerate(ids)}
        for cid, r in llm.items():
            j = id_to_row.get(cid)
            if j is not None:
                S_llm[j] = float(r.get("fit_score", 0)) / 100.0
                S_rule[j] = float(r.get("fit_score", 0)) / 100.0  # rule-derived in deterministic mode

    extra = np.column_stack([S_dense, S_bm25, S_rule, S_llm, behav, emb_jd, lex]).astype(np.float32)
    X = np.column_stack([det, extra]).astype(np.float32)
    names = det_names + EXTRA_FEATURES
    return ids, X, names, dict(S_dense=S_dense, S_bm25=S_bm25, S_rule=S_rule, S_llm=S_llm)


def monotone_vec(names):
    signs = []
    for nm in names:
        if nm in feat.MONOTONE:
            signs.append(feat.MONOTONE[nm])
        elif nm in ("S_dense", "S_bm25", "S_rule", "S_llm", "behavioral_composite",
                    "emb_cos_jd_overall", "lexical_cos_jd"):
            signs.append(1)
        else:
            signs.append(0)
    return signs


def export_trees(booster, n_features: int):
    """Flatten XGBoost trees to numpy arrays for the pure-numpy evaluator."""
    df = booster.trees_to_dataframe()
    trees = []
    for tid, g in df.groupby("Tree"):
        nodes = {}
        for _, row in g.iterrows():
            nodes[row["ID"]] = row
        # map node IDs to local indices
        ids_local = list(g["ID"])
        idmap = {nid: i for i, nid in enumerate(ids_local)}
        feat_idx, thr, left, right, leaf = [], [], [], [], []
        for nid in ids_local:
            row = nodes[nid]
            if row["Feature"] == "Leaf":
                feat_idx.append(-1); thr.append(0.0); left.append(-1); right.append(-1)
                leaf.append(float(row["Gain"]))
            else:
                fi = int(row["Feature"].replace("f", "")) if str(row["Feature"]).startswith("f") else 0
                feat_idx.append(fi); thr.append(float(row["Split"]))
                left.append(idmap[row["Yes"]]); right.append(idmap[row["No"]])
                leaf.append(0.0)
        trees.append((feat_idx, thr, left, right, leaf))
    return trees


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    args = ap.parse_args()
    A = args.artifacts_dir

    ids, X, names, subs = assemble_matrix(A)
    tiers = np.load(os.path.join(A, "proxy_tiers.npy")).astype(np.float32)
    # rank:ndcg in xgboost >=2 requires INTEGER relevance degrees (0..5); keep a float copy
    # for the NDCG math and an int copy for the DMatrix labels.
    tiers_int = np.load(os.path.join(A, "proxy_tiers.npy")).astype(np.int32)
    n = len(ids)

    # the fixed-weight blend baseline (what we ship if LTR doesn't win)
    blend = (0.50 * subs["S_llm"] + 0.20 * subs["S_dense"]
             + 0.18 * subs["S_rule"] + 0.12 * subs["S_bm25"])
    blend_ndcg = ndcg_at_k(tiers, blend, 10)

    use_ltr = False
    ltr_ndcg = 0.0
    try:
        import xgboost as xgb
        from sklearn.model_selection import KFold

        mono = monotone_vec(names)
        params = dict(objective="rank:ndcg", eval_metric="ndcg@10", eta=0.1, max_depth=4,
                      min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
                      monotone_constraints="(" + ",".join(str(s) for s in mono) + ")",
                      tree_method="hist", seed=0)
        # 5-fold CV NDCG@10 (single group per fold = whole-list ranking)
        kf = KFold(n_splits=min(5, max(2, n // 10)), shuffle=True, random_state=0)
        scores = []
        for tr, te in kf.split(X):
            dtr = xgb.DMatrix(X[tr], label=tiers_int[tr])
            dtr.set_group([len(tr)])
            dte = xgb.DMatrix(X[te])
            bst = xgb.train(params, dtr, num_boost_round=60, verbose_eval=False)
            pred = bst.predict(dte)
            scores.append(ndcg_at_k(tiers[te], pred, 10))
        ltr_ndcg = float(np.mean(scores))

        # train final on all data and export
        dall = xgb.DMatrix(X, label=tiers_int)
        dall.set_group([n])
        final = xgb.train(params, dall, num_boost_round=80, verbose_eval=False)
        trees = export_trees(final, len(names))

        use_ltr = ltr_ndcg >= blend_ndcg
        if use_ltr:
            # pad ragged trees into rectangular arrays
            maxlen = max(len(t[0]) for t in trees)
            T = len(trees)
            fa = np.full((T, maxlen), -1, dtype=np.int32)
            th = np.zeros((T, maxlen), dtype=np.float32)
            lf = np.full((T, maxlen), -1, dtype=np.int32)
            rt = np.full((T, maxlen), -1, dtype=np.int32)
            lv = np.zeros((T, maxlen), dtype=np.float32)
            for ti, (feat_idx, thr, left, right, leaf) in enumerate(trees):
                k = len(feat_idx)
                fa[ti, :k] = feat_idx; th[ti, :k] = thr
                lf[ti, :k] = left; rt[ti, :k] = right; lv[ti, :k] = leaf
            np.savez(os.path.join(A, "ltr_trees.npz"),
                     feature=fa, threshold=th, left=lf, right=rt, leaf=lv,
                     base_score=np.float32(0.5))
            manifest_add("ltr_trees", os.path.join(A, "ltr_trees.npz"), "precompute/train_ltr.py", A)
    except Exception as e:  # noqa: BLE001
        print(f"LTR training unavailable ({type(e).__name__}: {e}); shipping blend.")

    save_json(os.path.join(A, "ltr_model.json"),
              {"feature_order": names, "n_features": len(names), "use_ltr": use_ltr})
    save_json(os.path.join(A, "calibration.json"), {
        "use_ltr": use_ltr,
        "blend_weights": {"S_llm": 0.50, "S_dense": 0.20, "S_rule": 0.18, "S_bm25": 0.12},
        "longtail_weights": {"S_rule": 0.50, "S_dense": 0.30, "S_bm25": 0.20, "ceiling": 0.85},
        "cv_ndcg": {"ltr": ltr_ndcg, "blend": blend_ndcg},
    })
    manifest_add("ltr_model", os.path.join(A, "ltr_model.json"), "precompute/train_ltr.py", A)
    manifest_add("calibration", os.path.join(A, "calibration.json"), "precompute/train_ltr.py", A)

    print(f"CV-NDCG@10: blend={blend_ndcg:.4f} ltr={ltr_ndcg:.4f} -> ship "
          f"{'LTR' if use_ltr else 'BLEND'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
