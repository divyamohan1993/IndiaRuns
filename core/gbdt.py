"""Pure-numpy frozen-tree evaluator (Plane B; no xgboost at rank time).

Loads ltr_trees.npz (rectangular arrays produced by precompute/train_ltr.py) and scores
a feature matrix. Matches XGBoost's `Yes = feature < threshold` convention and adds
base_score once. Vectorized across all rows per tree.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np


class FrozenGBDT:
    def __init__(self, feature: np.ndarray, threshold: np.ndarray, left: np.ndarray,
                 right: np.ndarray, leaf: np.ndarray, base_score: float = 0.5):
        self.feature = feature      # (T, M) int; -1 == leaf
        self.threshold = threshold  # (T, M) float
        self.left = left            # (T, M) int; -1 == leaf/none
        self.right = right          # (T, M) int
        self.leaf = leaf            # (T, M) float
        self.base_score = float(base_score)
        self.n_trees = feature.shape[0]

    @classmethod
    def load(cls, path: str) -> Optional["FrozenGBDT"]:
        if not os.path.exists(path):
            return None
        z = np.load(path)
        base = float(z["base_score"]) if "base_score" in z else 0.5
        return cls(z["feature"], z["threshold"], z["left"], z["right"], z["leaf"], base)

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        n = X.shape[0]
        out = np.full(n, self.base_score, dtype=np.float64)
        for t in range(self.n_trees):
            fa, th, lf, rt, lv = (self.feature[t], self.threshold[t],
                                  self.left[t], self.right[t], self.leaf[t])
            node = np.zeros(n, dtype=np.int64)
            active = np.ones(n, dtype=bool)
            # iterate until all rows reach a leaf (depth-bounded; trees are shallow)
            for _ in range(64):
                if not active.any():
                    break
                cur = node[active]
                is_leaf = fa[cur] == -1
                # rows that just reached a leaf drop out
                done_idx = np.where(active)[0][is_leaf]
                if len(done_idx):
                    out[done_idx] += lv[node[done_idx]]
                    active[done_idx] = False
                cur_idx = np.where(active)[0]
                if len(cur_idx) == 0:
                    break
                cur = node[cur_idx]
                feat_vals = X[cur_idx, fa[cur]]
                go_left = feat_vals < th[cur]
                node[cur_idx] = np.where(go_left, lf[cur], rt[cur])
        return out.astype(np.float32)
