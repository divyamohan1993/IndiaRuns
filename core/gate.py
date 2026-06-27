"""Honeypot gate + anti-trap multiplicative caps + top-10 paranoia (Plane B).

Three layers (spec §3):
  L1 frozen hard-exclude  -> margin = -inf
  L2 live re-verify of survivors (top-300 by margin) -> -inf if any clean signature
  L3 top-10 paranoia: each top-10 slot must have 0 clean signatures + Group-A evidence>0

Anti-trap caps (spec §4.3) are multiplicative on the margin so a disqualifier cannot be
out-bought by keywords. role_skill_mismatch (x0.15) is the deterministic FLOOR.
"""

from __future__ import annotations

import math
from typing import Dict, List

from core import honeypot

NEG_INF = -1e18


def anti_trap_multiplier(det: Dict[str, float]) -> float:
    """Product of applicable caps from the deterministic feature dict."""
    m = 1.0
    # THE trap: non-eng title AND >=1 AI skill -> x0.15 (the floor under any LLM optimism)
    if det.get("non_eng_title_flag", 0) >= 1.0 and det.get("ai_skill_count", 0) >= 1.0:
        m *= 0.15
    if det.get("services_only_flag", 0) >= 1.0:
        # graded by services_fraction within [0.55, 0.85]
        frac = det.get("services_fraction", 1.0)
        m *= max(0.55, 0.85 - 0.30 * frac)
    if det.get("title_chaser_flag", 0) >= 1.0:
        m *= 0.70
    if det.get("cv_speech_robo_no_nlp", 0) >= 1.0:
        m *= 0.50
    if det.get("recent_langchain_only", 0) >= 1.0:
        m *= 0.60
    if det.get("pure_research_flag", 0) >= 1.0:
        m *= 0.50
    return max(m, 1e-6)  # floored so order is preserved


def apply_hard_gate(margin: float, cid: str, frozen_exclude: set) -> float:
    return NEG_INF if cid in frozen_exclude else margin


def reverify_survivor(c: Dict, company_first=None) -> bool:
    """True == clean (no clean structural signature). Salary inversion excluded by design."""
    return len(honeypot.clean_signatures(c, company_first=company_first)) == 0


def group_a_evidence(det: Dict[str, float]) -> float:
    return (det.get("evid_ranking_search_reco", 0) + det.get("evid_embeddings_vectordb", 0)
            + det.get("evid_eval_framework", 0) + det.get("evid_production_deploy", 0)
            + det.get("evid_built_endto_end", 0))


def top10_ok(c: Dict, det: Dict[str, float], frozen_exclude: set, company_first=None) -> bool:
    cid = c.get("candidate_id", "")
    if cid in frozen_exclude:
        return False
    if not reverify_survivor(c, company_first=company_first):
        return False
    if group_a_evidence(det) <= 0:
        return False
    return True
