"""Isotonic calibration (pure numpy) + min-max rescale to [0,1].

Used to map raw margins to a monotone, well-spread score. The isotonic fit is done
offline; rank.py only applies a frozen step function (or, absent one, a min-max rescale).
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def isotonic_fit(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Pool-adjacent-violators isotonic regression. Returns (x_sorted, y_fitted)."""
    order = np.argsort(x, kind="mergesort")
    xs = x[order].astype(np.float64)
    ys = y[order].astype(np.float64)
    w = np.ones_like(ys)
    # PAVA
    vals: List[float] = []
    weights: List[float] = []
    for yi, wi in zip(ys, w):
        vals.append(yi); weights.append(wi)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            v2, w2 = vals.pop(), weights.pop()
            v1, w1 = vals.pop(), weights.pop()
            nw = w1 + w2
            vals.append((v1 * w1 + v2 * w2) / nw); weights.append(nw)
    fitted = []
    for v, wi in zip(vals, weights):
        fitted.extend([v] * int(wi))
    return xs, np.asarray(fitted[: len(xs)])


def rescale01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    lo, hi = float(x.min()), float(x.max())
    if hi - lo <= 0:
        return np.full_like(x, 0.5)
    return (x - lo) / (hi - lo)
