"""Final score assembly + top-100 selection + CSV write with validator pre-flight.

Pure numpy + stdlib. Implements spec §2.6-2.7 + §5 behavioral multiplier + §3 gate layers.
The sort key is (-final, candidate_id) so equal scores tie-break by candidate_id ASC,
exactly what the vendored validator requires. The printed score column is clamped
non-increasing before writing (commit-21 robustness).
"""

from __future__ import annotations

import csv
import math
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from core import gate
from core.calibrate import rescale01


def behavioral_multiplier(det: Dict[str, float], c: Dict) -> float:
    """clip(1 + sum(contributions), 0.80, 1.12). Sentinels contribute exactly 0."""
    from core.schema import github_activity, offer_acceptance, recruiter_response_rate

    contrib = 0.0
    rr = recruiter_response_rate(c)
    if rr is not None:
        contrib += 0.10 * (rr - 0.44) / 0.32
    contrib += {1.0: 0.05, 0.6: 0.0}.get(det.get("recency_score", 0.3), -0.08 if det.get("recency_score", 0.3) < 0.6 else 0.0)
    if det.get("open_to_work_flag", 0) >= 1.0:
        contrib += 0.05
    nf = det.get("notice_fit", 0.5)
    contrib += 0.04 if nf >= 1.0 else (0.0 if nf >= 0.5 else -0.04)
    contrib += 0.03 * (det.get("interview_completion_rate", 0.5) - 0.5)
    contrib += 0.03 * (0.5 * det.get("verified_email", 0) + 0.5 * det.get("verified_phone", 0))
    contrib += 0.03 * det.get("saved_by_recruiters_30d_log", 0)
    contrib += 0.02 * det.get("profile_completeness_norm", 0)
    # sentinel-gated extras: contribute ONLY when present (never penalize when -1)
    gh = github_activity(c)
    if gh.present and gh.value > 0:
        contrib += 0.03 * min(1.0, math.log1p(gh.value) / math.log1p(100))
    oa = offer_acceptance(c)
    if oa.present and oa.value > 0:
        contrib += 0.02 * oa.value
    return float(min(1.12, max(0.80, 1.0 + contrib)))


def assemble_final(
    cids: List[str],
    margins: np.ndarray,
    dets: List[Dict[str, float]],
    cands: List[Dict],
    frozen_exclude: set,
    company_first: Optional[dict] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply anti-trap caps + behavioral multiplier + hard gate + survivor re-verify.

    Returns (final_scores, role_prime) as float arrays aligned to cids.
    """
    n = len(cids)
    final = np.array(margins, dtype=np.float64)
    role_prime = np.zeros(n, dtype=np.float64)
    # rank survivors for L2 re-verify (top-300 by margin)
    survivor_cut = set(np.argsort(-final)[:300].tolist())
    for i in range(n):
        atm = gate.anti_trap_multiplier(dets[i])
        rp = final[i] * atm
        role_prime[i] = rp
        bm = behavioral_multiplier(dets[i], cands[i])
        f = rp * bm
        if cids[i] in frozen_exclude:
            f = gate.NEG_INF
        elif i in survivor_cut and not gate.reverify_survivor(cands[i], company_first=company_first):
            f = gate.NEG_INF
        final[i] = f
    return final, role_prime


def select_top100_with_paranoia(
    cids: List[str], final: np.ndarray, dets: List[Dict[str, float]],
    cands: List[Dict], frozen_exclude: set, company_first: Optional[dict] = None,
) -> List[int]:
    """Return indices of the chosen top-100 in rank order, after top-10 paranoia swaps."""
    order = sorted(range(len(cids)), key=lambda i: (-final[i], cids[i]))
    order = [i for i in order if final[i] > gate.NEG_INF / 2]
    top = order[:100]
    rest = order[100:]

    def _ok(i: int) -> bool:
        return gate.top10_ok(cands[i], dets[i], frozen_exclude, company_first=company_first)

    # top-10 paranoia as a FIXPOINT: re-sort, then re-verify the final top-10; whenever a
    # final top-10 slot fails, swap it out for the highest-scoring qualifying replacement and
    # repeat. A plain single pass is insufficient because the post-swap re-sort can promote an
    # original slot-11+ candidate (never top-10-checked) into the final top-10. Bounded by the
    # number of candidates and fully deterministic (rest stays score-ordered; ties by id).
    top = sorted(top, key=lambda i: (-final[i], cids[i]))
    while True:
        changed = False
        for slot in range(min(10, len(top))):
            i = top[slot]
            if _ok(i):
                continue
            for j_pos, j in enumerate(rest):
                if _ok(j):
                    top[slot] = j
                    rest.pop(j_pos)
                    # return the displaced candidate to the score-ordered remainder
                    rest.append(i)
                    rest.sort(key=lambda k: (-final[k], cids[k]))
                    top = sorted(top, key=lambda k: (-final[k], cids[k]))
                    changed = True
                    break
            else:
                # no qualifying replacement remains; leave the slot as-is
                continue
            break  # re-sort happened; restart the scan from the top
        if not changed:
            break
    return top[:100]


def to_rows(cids: List[str], final: np.ndarray, chosen: List[int],
            reasoning_fn: Callable[[int], str]) -> List[Tuple[str, int, float, str]]:
    """Build (candidate_id, rank, score, reasoning) rows with a clamped non-increasing
    score column and id-ascending tie order already guaranteed by `chosen` ordering."""
    sub = np.array([final[i] for i in chosen], dtype=np.float64)
    scores01 = rescale01(sub) if len(sub) else sub
    rows = []
    prev = None
    for rank, (i, s01) in enumerate(zip(chosen, scores01), start=1):
        score = round(float(s01), 6)
        if prev is not None and score > prev:
            score = prev  # clamp non-increasing
        prev = score
        rows.append((cids[i], rank, score, reasoning_fn(i)))
    return rows


def write_csv(path: str, rows: List[Tuple[str, int, float, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for cid, rank, score, reason in rows:
            w.writerow([cid, rank, f"{score:.6f}", reason])


def preflight_validate(path: str) -> List[str]:
    """Run the vendored validator's logic on our own output before trusting it."""
    import importlib.util
    import os
    vpath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "validate_submission.py")
    spec = importlib.util.spec_from_file_location("validate_submission", vpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_submission(path)
