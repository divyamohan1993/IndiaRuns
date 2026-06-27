"""JD-encoded rule-fit: the deterministic role-fit logic that carries the JD's MEANING.

Two outputs from the same logic (ported from the probe's tier_proxy.py + spec §4):
  - proxy_tier(c)  -> int 0..5  (INTERNAL relevance proxy for NDCG eval / LTR labels;
                                 NEVER a ground truth)
  - rule_fit(c)    -> float [0,1]  (the S_rule sub-score used in fusion)

Shared by precompute/make_labels.py and by features/score at rank time, so the rule
the LTR trains on is exactly the rule the ranker applies (no skew).
"""

from __future__ import annotations

from typing import Dict, Tuple

from core import honeypot, keywords
from core.schema import (
    NOW,
    career,
    current_industry,
    current_title,
    last_active,
    lower,
    open_to_work,
    profile,
    recruiter_response_rate,
    years_of_experience,
)


def _context(c: Dict) -> dict:
    p = profile(c)
    title = current_title(c)
    ind = current_industry(c)
    y = years_of_experience(c)
    skills_txt = " ".join(lower(s.get("name")) for s in c.get("skills", []) if isinstance(s, dict))
    career_txt = " ".join((lower(j.get("title")) + " " + lower(j.get("description")))
                          for j in career(c) if isinstance(j, dict))
    summ = lower(p.get("summary")) + " " + lower(p.get("headline"))
    blob = skills_txt + " " + career_txt + " " + summ

    comps = [lower(j.get("company")) for j in career(c) if isinstance(j, dict)]
    services_only = bool(comps) and all(any(sv in cn for sv in keywords.SERVICES_FIRMS) for cn in comps)
    has_product = any(h in ind for h in keywords.PRODUCT_INDUSTRY_HINTS) or any(
        any(h in lower(j.get("industry")) for h in keywords.PRODUCT_INDUSTRY_HINTS)
        for j in career(c) if isinstance(j, dict))

    ai_title = keywords.any_in(title, keywords.AI_TITLE)
    rank_ev = keywords.any_in(blob, keywords.RANK_EVIDENCE)
    cv_speech = keywords.any_in(blob, keywords.CV_SPEECH_ROBO)
    nlp_ir = keywords.any_in(blob, keywords.NLP_IR)
    eng_title = keywords.any_in(title, keywords.ENG_TITLE)
    non_eng = keywords.any_in(title, keywords.NON_ENG_TITLE)

    rr = recruiter_response_rate(c)
    la = last_active(c)
    stale = (la is None) or ((NOW - la).days > 180)
    otw = open_to_work(c)
    active = (otw or (rr is not None and rr >= 0.25)) and not stale

    durs = [j.get("duration_months") for j in career(c)
            if isinstance(j, dict) and isinstance(j.get("duration_months"), (int, float))
            and not isinstance(j.get("duration_months"), bool)]
    hops = sum(1 for d in durs if d <= 20)
    title_chaser = len(durs) >= 3 and hops >= 3

    return dict(title=title, blob=blob, skills_txt=skills_txt, y=y,
                services_only=services_only, has_product=has_product,
                ai_title=ai_title, rank_ev=rank_ev, cv_speech=cv_speech, nlp_ir=nlp_ir,
                eng_title=eng_title, non_eng=non_eng, active=active, title_chaser=title_chaser)


def proxy_tier(c: Dict, company_first=None) -> Tuple[int, str]:
    """Return (tier 0..5, reason). INTERNAL eval proxy only."""
    if honeypot.is_honeypot(c, company_first=company_first):
        return 0, "honeypot/structural-impossibility"
    x = _context(c)

    if x["cv_speech"] and not (x["nlp_ir"] or x["rank_ev"]):
        return 1, "CV/speech/robotics without NLP-IR exposure"

    if x["non_eng"]:
        has_ai = x["rank_ev"] or keywords.any_in(x["skills_txt"], keywords.NLP_IR)
        return (1 if has_ai else 0), "non-eng title w/ AI keywords = keyword-stuffer trap"

    score = 2
    if x["eng_title"]:
        score = 3
    if (x["ai_title"] or x["rank_ev"]) and x["eng_title"]:
        score = 4
    if (x["ai_title"] or x["rank_ev"]) and x["has_product"] and not x["services_only"]:
        score = 5
    if x["services_only"]:
        score = min(score, 2)
    if x["title_chaser"]:
        score = min(score, 3)
    if not (4 <= x["y"] <= 10):
        score = min(score, 4)
    if not x["active"]:
        score = min(score, 3)
    if "langchain" in x["blob"] and x["y"] < 3 and not x["rank_ev"]:
        score = min(score, 3)
    return score, "computed"


def rule_fit(c: Dict, company_first=None) -> float:
    """Continuous S_rule in [0,1] derived from the same tier logic, with smooth credit
    for career evidence so it discriminates within a tier."""
    if honeypot.is_honeypot(c, company_first=company_first):
        return 0.0
    tier, _ = proxy_tier(c, company_first=company_first)
    base = tier / 5.0
    x = _context(c)
    # within-tier nudge from concrete evidence (bounded so it can't cross tiers far)
    evid = (keywords.count_in(x["blob"], keywords.EVID_RANKING_SEARCH_RECO)
            + keywords.count_in(x["blob"], keywords.EVID_EMBEDDINGS_VECTORDB)
            + keywords.count_in(x["blob"], keywords.EVID_EVAL_FRAMEWORK))
    nudge = min(0.08, 0.02 * evid)
    return float(min(1.0, base + nudge))
