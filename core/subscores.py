"""Compute the four normalized sub-scores from frozen artifacts (pure numpy).

Shared by precompute/first_pass_shortlist.py and Plane-B rank.py so the dense/bm25/rule
definitions never diverge. No network, no model — only matrix ops over loaded arrays.

  S_dense : per-clause weighted pool of cosines + 0.25*ideal, blended 0.5/0.5 with the
            pool-percentile rank (backend-scale robust).
  S_bm25  : frozen bm25.npz (already [0,1]).
  S_rule  : per-candidate rule_fit (computed from the streamed record, [0,1]).
  role_title_cos : cosine of candidate vector vs the AI-role-title anchor.
"""

from __future__ import annotations

import numpy as np


def _percentile_rank(x: np.ndarray) -> np.ndarray:
    """Map values to their [0,1] rank-percentile (ties share the average position)."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(len(x), dtype=np.float64)
    n = max(len(x) - 1, 1)
    return ranks / n


def dense_scores(cand_emb: np.ndarray, clauses: np.ndarray, weights: np.ndarray,
                 ideal: np.ndarray, ideal_lambda: float = 0.25) -> np.ndarray:
    """cand_emb: (N,D) L2-normalized. clauses: (C,D). ideal: (1,D) or (D,)."""
    cand = cand_emb.astype(np.float32)
    C = clauses.astype(np.float32)
    w = weights.astype(np.float32)
    cos = cand @ C.T  # (N, C)
    cos = np.maximum(0.0, cos)
    pooled = cos @ w  # (N,)
    ideal = np.asarray(ideal, dtype=np.float32).reshape(-1)
    pooled = pooled + ideal_lambda * np.maximum(0.0, cand @ ideal)
    # normalize raw pooled to [0,1] then blend with its percentile rank
    rng = pooled.max() - pooled.min()
    raw01 = (pooled - pooled.min()) / rng if rng > 0 else np.zeros_like(pooled)
    pct = _percentile_rank(pooled)
    return (0.5 * raw01 + 0.5 * pct).astype(np.float32)


def role_title_cos(cand_emb: np.ndarray, role_anchor: np.ndarray) -> np.ndarray:
    ra = np.asarray(role_anchor, dtype=np.float32).reshape(-1)
    cos = cand_emb.astype(np.float32) @ ra
    return np.clip((cos + 1) / 2, 0, 1).astype(np.float32)


def first_pass(S_dense: np.ndarray, S_bm25: np.ndarray, S_rule: np.ndarray) -> np.ndarray:
    """Recall-weighted first pass (spec §2.4): meaning leads."""
    return (0.30 * S_dense + 0.25 * S_bm25 + 0.45 * S_rule).astype(np.float32)


def base_fit_shortlisted(S_llm, S_dense, S_rule, S_bm25) -> np.ndarray:
    return (0.50 * S_llm + 0.20 * S_dense + 0.18 * S_rule + 0.12 * S_bm25).astype(np.float32)


def base_fit_longtail(S_rule, S_dense, S_bm25) -> np.ndarray:
    return ((0.50 * S_rule + 0.30 * S_dense + 0.20 * S_bm25) * 0.85).astype(np.float32)
