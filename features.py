"""Shared deterministic feature extractor (Plane A & Plane B import THIS module).

No train/serve skew: the exact same code computes features when building
cand_features.f16.npy offline and when re-deriving live signals at rank time.

Groups (spec §4.2):
  A — career-evidence (monotone +)
  B — role-fit (mixed; includes ai_skill_x_non_eng, the keyword-stuffer detector, -)
  C — anti-pattern penalties (monotone -)
  D — behavioral (monotone +)
  E — honeypot flags (monotone -; the two demoted ones are SOFT)
  F — semantic (filled in by precompute; placeholders here so the vector width is stable)

`FEATURE_NAMES` defines the canonical order. `extract(c)` returns a list[float] of the
deterministic (non-semantic) features; semantic features (Group F) are appended by the
precompute embed step and by rank.py from frozen embeddings, keyed by the same names.
"""

from __future__ import annotations

import math
from typing import Dict, List

from core import honeypot, keywords
from core.schema import (
    career, current_industry, current_title, country, education, last_active,
    NOW, notice_period_days, open_to_work, profile, recruiter_response_rate,
    salary_range, signals, skill_assessment_scores, skills, years_of_experience,
    github_activity, offer_acceptance, fnum, inum, fbool, lower,
)

# ----------------------------------------------------------------------------
# Canonical feature order + monotone signs (+1/-1/0). 0 == no monotone constraint.
# ----------------------------------------------------------------------------
# Group A — career-evidence
A_FEATURES = [
    ("evid_ranking_search_reco", +1),
    ("evid_embeddings_vectordb", +1),
    ("evid_eval_framework", +1),
    ("evid_production_deploy", +1),
    ("evid_built_endto_end", +1),
    ("evid_quote_strength", +1),  # LLM-derived (A6); 0 without LLM
]
# Group B — role-fit
B_FEATURES = [
    ("ai_title_flag", +1),
    ("eng_title_flag", +1),
    ("non_eng_title_flag", -1),
    ("ai_skill_count", 0),          # NOT monotone — trap axis
    ("ai_skill_x_non_eng", -1),     # the keyword-stuffer detector
    ("skill_trust", +1),
    ("assessment_corroboration", +1),
    ("jd_facet_coverage", +1),
]
# Group C — anti-pattern penalties
C_FEATURES = [
    ("services_only_flag", -1),
    ("services_fraction", -1),
    ("title_chaser_flag", -1),
    ("median_tenure_months", +1),
    ("cv_speech_robo_no_nlp", -1),
    ("recent_langchain_only", -1),
    ("pure_research_flag", -1),
    ("no_external_validation", -1),
    ("out_of_band_yoe", -1),
]
# Group D — behavioral
D_FEATURES = [
    ("resp_rate_norm", +1),
    ("recency_score", +1),
    ("open_to_work_flag", +1),
    ("notice_fit", +1),
    ("interview_completion_rate", +1),
    ("saved_by_recruiters_30d_log", +1),
    ("profile_completeness_norm", +1),
    ("verified_email", +1),
    ("verified_phone", +1),
    ("availability_composite", +1),
]
# Group E — honeypot flags
E_FEATURES = [
    ("hp_hard_flag", -1),
    ("hp_signature_count", -1),
    ("too_many_experts", -1),
    ("expert_zero_duration", -1),
    ("career_sum_exceeds_yoe", -1),
    ("skill_dur_exceeds_career_soft", -1),  # SOFT
    ("edu_order_soft", -1),                 # SOFT
]
# Group F — semantic (filled by precompute / rank.py from frozen embeddings)
F_FEATURES = [
    ("emb_cos_retrieval", +1),
    ("emb_cos_ranking_ltr", +1),
    ("emb_cos_product_shipping", +1),
    ("emb_cos_jd_overall", +1),
    ("svd_1", 0), ("svd_2", 0), ("svd_3", 0), ("svd_4", 0),
    ("svd_5", 0), ("svd_6", 0), ("svd_7", 0),
    ("lexical_cos_jd", +1),
]

DETERMINISTIC_FEATURES = A_FEATURES + B_FEATURES + C_FEATURES + D_FEATURES + E_FEATURES
ALL_FEATURES = DETERMINISTIC_FEATURES + F_FEATURES
FEATURE_NAMES = [n for n, _ in ALL_FEATURES]
DET_FEATURE_NAMES = [n for n, _ in DETERMINISTIC_FEATURES]
MONOTONE = {n: s for n, s in ALL_FEATURES}
N_FEATURES = len(FEATURE_NAMES)
N_DET = len(DET_FEATURE_NAMES)


# ----------------------------------------------------------------------------
# Text assembly (the narrative; descriptions weighted above skills)
# ----------------------------------------------------------------------------

def narrative_text(c: Dict) -> str:
    """The career narrative used for embeddings + BM25. Descriptions dominate; the
    skills clause is appended last (and once) so keyword-stuffing can't move the vector."""
    p = profile(c)
    parts: List[str] = []
    if p.get("headline"):
        parts.append(str(p["headline"]))
    if p.get("summary"):
        parts.append(str(p["summary"]))
    for j in career(c):
        if not isinstance(j, dict):
            continue
        t = j.get("title", "") or ""
        co = j.get("company", "") or ""
        ind = j.get("industry", "") or ""
        desc = j.get("description", "") or ""
        parts.append(f"{t} at {co} ({ind}): {desc}")
    sk = ", ".join(str(s.get("name", "")) for s in skills(c) if isinstance(s, dict))
    if sk:
        parts.append(f"Skills: {sk}")
    return "\n".join(parts)


def _career_blob(c: Dict) -> str:
    parts = []
    for j in career(c):
        if isinstance(j, dict):
            parts.append(lower(j.get("title")) + " " + lower(j.get("description")))
    p = profile(c)
    parts.append(lower(p.get("summary")) + " " + lower(p.get("headline")))
    return " ".join(parts)


def _skills_blob(c: Dict) -> str:
    return " ".join(lower(s.get("name")) for s in skills(c) if isinstance(s, dict))


# ----------------------------------------------------------------------------
# Group computations
# ----------------------------------------------------------------------------

def _services_stats(c: Dict):
    comps = [lower(j.get("company")) for j in career(c) if isinstance(j, dict)]
    if not comps:
        return False, 0.0
    flags = [any(sv in cn for sv in keywords.SERVICES_FIRMS) for cn in comps]
    frac = sum(flags) / len(flags)
    services_only = all(flags)
    return services_only, frac


def _has_product(c: Dict) -> bool:
    if any(h in current_industry(c) for h in keywords.PRODUCT_INDUSTRY_HINTS):
        return True
    for j in career(c):
        if isinstance(j, dict) and any(h in lower(j.get("industry")) for h in keywords.PRODUCT_INDUSTRY_HINTS):
            return True
    return False


def _durations(c: Dict) -> List[float]:
    return [float(j["duration_months"]) for j in career(c)
            if isinstance(j, dict) and isinstance(j.get("duration_months"), (int, float))
            and not isinstance(j.get("duration_months"), bool)]


def _median(xs: List[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def extract_det(c: Dict, company_first=None) -> Dict[str, float]:
    """Return the deterministic feature dict (Groups A-E). Group F is added elsewhere."""
    p = profile(c)
    title = current_title(c)
    blob = _career_blob(c)
    skills_blob = _skills_blob(c)
    full = blob + " " + skills_blob
    y = years_of_experience(c)
    f: Dict[str, float] = {}

    # ---- Group A: career evidence (over descriptions/narrative, not skills array) ----
    f["evid_ranking_search_reco"] = float(keywords.count_in(blob, keywords.EVID_RANKING_SEARCH_RECO))
    f["evid_embeddings_vectordb"] = float(keywords.count_in(blob, keywords.EVID_EMBEDDINGS_VECTORDB))
    f["evid_eval_framework"] = float(keywords.count_in(blob, keywords.EVID_EVAL_FRAMEWORK))
    f["evid_production_deploy"] = float(min(3, keywords.count_in(blob, keywords.EVID_PRODUCTION_DEPLOY)))
    f["evid_built_endto_end"] = float(min(3, keywords.count_in(blob, keywords.EVID_BUILT_ENDTOEND)))
    f["evid_quote_strength"] = 0.0  # LLM-derived; 0 without LLM re-rank

    # ---- Group B: role fit ----
    ai_title = keywords.any_in(title, keywords.AI_TITLE)
    eng_title = keywords.any_in(title, keywords.ENG_TITLE)
    non_eng = keywords.any_in(title, keywords.NON_ENG_TITLE)
    ai_skill_count = keywords.count_in(skills_blob, keywords.AI_SKILL)
    f["ai_title_flag"] = 1.0 if ai_title else 0.0
    f["eng_title_flag"] = 1.0 if eng_title else 0.0
    f["non_eng_title_flag"] = 1.0 if non_eng else 0.0
    f["ai_skill_count"] = float(ai_skill_count)
    f["ai_skill_x_non_eng"] = float(ai_skill_count) * (1.0 if non_eng else 0.0)
    # skill_trust = sum(proficiency_weight * log1p(endorsements) * min(dur,60)/60)
    prof_w = {"beginner": 0.25, "intermediate": 0.5, "advanced": 0.8, "expert": 1.0}
    trust = 0.0
    for s in skills(c):
        if not isinstance(s, dict):
            continue
        w = prof_w.get(s.get("proficiency"), 0.4)
        end = math.log1p(max(0, inum(s.get("endorsements"))))
        dur = min(60.0, fnum(s.get("duration_months"))) / 60.0
        trust += w * end * dur
    f["skill_trust"] = float(min(trust, 50.0))
    # assessment corroboration: avg skill-assessment score / 100
    asc = skill_assessment_scores(c)
    f["assessment_corroboration"] = float(sum(asc.values()) / len(asc) / 100.0) if asc else 0.0
    # jd_facet_coverage: distinct evidence facets present (of 5)
    facets = sum(1 for grp in (keywords.EVID_RANKING_SEARCH_RECO, keywords.EVID_EMBEDDINGS_VECTORDB,
                               keywords.EVID_EVAL_FRAMEWORK, keywords.EVID_PRODUCTION_DEPLOY,
                               keywords.EVID_BUILT_ENDTOEND) if keywords.any_in(blob, grp))
    f["jd_facet_coverage"] = facets / 5.0

    # ---- Group C: anti-patterns ----
    services_only, services_frac = _services_stats(c)
    has_product = _has_product(c)
    # a prior product stint removes the services-only flag
    f["services_only_flag"] = 1.0 if (services_only and not has_product) else 0.0
    f["services_fraction"] = float(services_frac)
    durs = _durations(c)
    hops = sum(1 for d in durs if d <= 20)
    f["title_chaser_flag"] = 1.0 if (len(durs) >= 3 and hops >= 3) else 0.0
    f["median_tenure_months"] = float(min(_median(durs), 120.0))
    cv_speech = keywords.any_in(full, keywords.CV_SPEECH_ROBO)
    nlp_ir = keywords.any_in(full, keywords.NLP_IR)
    rank_ev = keywords.any_in(blob, keywords.RANK_EVIDENCE)
    f["cv_speech_robo_no_nlp"] = 1.0 if (cv_speech and not (nlp_ir or rank_ev)) else 0.0
    f["recent_langchain_only"] = 1.0 if (keywords.any_in(full, keywords.RECENT_LLM_ONLY)
                                         and y < 3 and not rank_ev) else 0.0
    f["pure_research_flag"] = 1.0 if (("research" in title or "phd" in blob)
                                      and not keywords.any_in(blob, keywords.EVID_PRODUCTION_DEPLOY)) else 0.0
    gh = github_activity(c)
    ext_val = (gh.present and gh.value > 0) or bool(c.get("certifications"))
    f["no_external_validation"] = 0.0 if ext_val else 1.0
    f["out_of_band_yoe"] = 1.0 if not (4.0 <= y <= 10.0) else 0.0

    # ---- Group D: behavioral ----
    rr = recruiter_response_rate(c)
    f["resp_rate_norm"] = float(max(0.0, min(1.0, (rr - 0.10) / (0.76 - 0.10)))) if rr is not None else 0.5
    la = last_active(c)
    if la is None:
        f["recency_score"] = 0.3
    else:
        months = (NOW - la).days / 30.44
        f["recency_score"] = 1.0 if months <= 3 else (0.6 if months <= 6 else 0.2)
    f["open_to_work_flag"] = 1.0 if open_to_work(c) else 0.0
    npd = notice_period_days(c)
    f["notice_fit"] = (1.0 if npd <= 30 else (0.5 if npd <= 60 else 0.1)) if npd is not None else 0.5
    icr = signals(c).get("interview_completion_rate")
    f["interview_completion_rate"] = float(icr) if isinstance(icr, (int, float)) and not isinstance(icr, bool) else 0.5
    saved = inum(signals(c).get("saved_by_recruiters_30d"))
    f["saved_by_recruiters_30d_log"] = float(min(math.log1p(max(0, saved)) / math.log1p(50), 1.0))
    pcs = fnum(signals(c).get("profile_completeness_score"))
    f["profile_completeness_norm"] = float(max(0.0, min(1.0, pcs / 100.0)))
    f["verified_email"] = 1.0 if fbool(signals(c).get("verified_email")) else 0.0
    f["verified_phone"] = 1.0 if fbool(signals(c).get("verified_phone")) else 0.0
    f["availability_composite"] = float((f["open_to_work_flag"] + f["notice_fit"]
                                         + f["recency_score"] + f["resp_rate_norm"]) / 4.0)

    # ---- Group E: honeypot flags ----
    clean = honeypot.clean_signatures(c, company_first=company_first)
    soft = honeypot.soft_signatures(c)
    f["hp_hard_flag"] = 1.0 if clean else 0.0
    f["hp_signature_count"] = float(len(clean))
    f["too_many_experts"] = 1.0 if "too_many_experts" in clean else 0.0
    f["expert_zero_duration"] = 1.0 if "expert_zero_duration" in clean else 0.0
    f["career_sum_exceeds_yoe"] = 1.0 if "career_sum_exceeds_yoe" in clean else 0.0
    f["skill_dur_exceeds_career_soft"] = 1.0 if "skill_duration_exceeds_career" in soft else 0.0
    f["edu_order_soft"] = 1.0 if "edu_degree_order_impossible" in soft else 0.0

    return f


def extract(c: Dict, company_first=None, semantic: Dict[str, float] | None = None) -> List[float]:
    """Full feature vector in FEATURE_NAMES order. Group F defaults to 0 unless `semantic`
    provides values (from frozen embeddings / lexical cosines)."""
    det = extract_det(c, company_first=company_first)
    sem = semantic or {}
    out: List[float] = []
    for name in FEATURE_NAMES:
        if name in det:
            out.append(det[name])
        else:
            out.append(float(sem.get(name, 0.0)))
    return out


def feature_meta() -> Dict:
    """The frozen feature metadata (names, monotone signs, group map)."""
    groups = {}
    for grp, lst in (("A", A_FEATURES), ("B", B_FEATURES), ("C", C_FEATURES),
                     ("D", D_FEATURES), ("E", E_FEATURES), ("F", F_FEATURES)):
        for n, _ in lst:
            groups[n] = grp
    return {
        "feature_names": FEATURE_NAMES,
        "monotone": MONOTONE,
        "groups": groups,
        "n_features": N_FEATURES,
        "n_deterministic": N_DET,
        "note": "Shared by Plane A and Plane B; identical code path (no train/serve skew). "
                "Salary inversion is deliberately NOT a feature.",
    }
