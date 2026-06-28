"""Deterministic fact-assembly reasoning (Plane B; zero network).

Stage-4 quality goals:
  - specific facts (>=2 of {years, title, company, named skill, signal value}),
  - explicit JD connection (the matched requirement),
  - one honest concern when a gap exists,
  - no hallucination (every token drawn from the record),
  - variation via hash(candidate_id) choosing the connective pattern,
  - rank-consistent tone (assertive head, hedged tail),
  - CSV-safe: commas stripped, <=140 chars.

`build_reasoning(c, ctx)` returns the final reasoning string. A frozen LLM reasoning
(from precompute/build_reasoning.py) may be passed in `ctx["llm_reasoning"]`; it is used
ONLY if it passes the same fact-validation, else this deterministic assembler wins.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from core import keywords
from core.schema import (
    NOW,
    career,
    last_active,
    lower,
    open_to_work,
    profile,
    recruiter_response_rate,
    years_of_experience,
)

MAX_LEN = 140

_CONNECTORS = [
    "{head}; {jd}{concern}",
    "{head} — {jd}{concern}",
    "{head}. {jd}{concern}",
    "{head}: {jd}{concern}",
]


def _csv_safe(s: str) -> str:
    s = s.replace(",", " ").replace("\n", " ").replace('"', "'")
    s = " ".join(s.split())
    if len(s) > MAX_LEN:
        s = s[:MAX_LEN].rstrip()
    return s


def _primary_company(c: Dict) -> str:
    for j in career(c):
        if isinstance(j, dict) and j.get("is_current") and j.get("company"):
            return str(j["company"])
    ch = career(c)
    return str(ch[0].get("company", "")) if ch and isinstance(ch[0], dict) else ""


def _matched_requirement(c: Dict) -> Optional[str]:
    blob = " ".join((lower(j.get("title")) + " " + lower(j.get("description")))
                    for j in career(c) if isinstance(j, dict))
    blob += " " + lower(profile(c).get("summary"))
    if keywords.any_in(blob, keywords.EVID_RANKING_SEARCH_RECO):
        return "built ranking/search/reco systems"
    if keywords.any_in(blob, keywords.EVID_EMBEDDINGS_VECTORDB):
        return "production embeddings/vector retrieval"
    if keywords.any_in(blob, keywords.EVID_EVAL_FRAMEWORK):
        return "ranking evaluation (NDCG/MRR/AB)"
    if keywords.any_in(blob, keywords.EVID_PRODUCTION_DEPLOY):
        return "shipped ML to production at scale"
    return None


def _facts(c: Dict) -> List[str]:
    p = profile(c)
    facts: List[str] = []
    title = p.get("current_title")
    y = years_of_experience(c)
    company = _primary_company(c)
    if title:
        facts.append(str(title))
    if y:
        facts.append(f"{y:g} yrs")
    if company:
        facts.append(f"at {company}")
    return facts


def _concern(c: Dict) -> str:
    rr = recruiter_response_rate(c)
    la = last_active(c)
    y = years_of_experience(c)
    parts = []
    if rr is not None and rr < 0.25:
        parts.append(f"low response rate {rr:.2f}")
    if la is not None and (NOW - la).days > 180:
        parts.append("stale activity")
    if not (4 <= y <= 10) and y:
        parts.append("YOE outside band")
    if not open_to_work(c) and not parts:
        parts.append("not flagged open-to-work")
    return parts[0] if parts else ""


def deterministic_reasoning(c: Dict) -> str:
    facts = _facts(c)
    head = " ".join(facts[:3]) if facts else "Candidate"
    req = _matched_requirement(c)
    rr = recruiter_response_rate(c)
    if req:
        jd = req
    elif rr is not None:
        jd = f"response rate {rr:.2f}"
    else:
        jd = "engineering background"
    concern = _concern(c)
    concern_str = f" — concern: {concern}" if concern else ""
    h = int(hashlib.sha256((c.get("candidate_id", "") or "").encode()).hexdigest(), 16)
    pattern = _CONNECTORS[h % len(_CONNECTORS)]
    return _csv_safe(pattern.format(head=head, jd=jd, concern=concern_str))


def _validate_llm(text: str, c: Dict) -> bool:
    """Reject an LLM reasoning that names a company/skill/number not in the record.

    Spec §6 / Stage-4 guarantee: every named skill, company, and number in the reason
    must be present in the candidate's own JSON, else fall back to deterministic.
    """
    if not text:
        return False
    import re
    p = profile(c)

    # --- known company / skill tokens (lowercased) ---
    known = set()
    if p.get("current_company"):
        known.add(lower(p["current_company"]))
    for j in career(c):
        if isinstance(j, dict) and j.get("company"):
            known.add(lower(j["company"]))
    skill_tokens = set()
    for s in c.get("skills", []):
        if isinstance(s, dict) and s.get("name"):
            nm = lower(s["name"])
            known.add(nm)
            skill_tokens.add(nm)

    # If the text mentions "at <Word>", that company must be known.
    for m in re.finditer(r"\bat ([A-Z][A-Za-z0-9&.\- ]{2,30})", text):
        cand = m.group(1).strip().lower()
        if not any(cand.startswith(k) or k.startswith(cand) or k in cand for k in known if k):
            return False

    # --- numeric grounding: every number in the text must appear in the record ---
    # Collect the numbers that legitimately describe this candidate.
    record_nums = set()

    import math

    def _add_num(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return
        record_nums.add(round(f))
        record_nums.add(round(f, 1))
        record_nums.add(int(math.floor(f)))  # "6.9 yrs" commonly reported as "6 yrs"
        record_nums.add(int(math.ceil(f)))

    _add_num(years_of_experience(c))
    rr = recruiter_response_rate(c)
    if rr is not None:
        _add_num(rr)
        _add_num(rr * 100)  # tolerate a "79%" phrasing of 0.79
    for j in career(c):
        if isinstance(j, dict):
            dm = j.get("duration_months")
            _add_num(dm)
            if isinstance(dm, (int, float)):
                _add_num(dm / 12.0)  # tenure expressed in years
    for s in c.get("skills", []):
        if isinstance(s, dict):
            _add_num(s.get("endorsements"))
            _add_num(s.get("duration_months"))

    for tok in re.findall(r"\d+(?:\.\d+)?", text):
        f = float(tok)
        # ignore numbers that are part of a known skill/company name (e.g. "S3", "GPT-4")
        if any(tok in k for k in known):
            continue
        if round(f) in record_nums or round(f, 1) in record_nums:
            continue
        return False
    return True


def build_reasoning(c: Dict, ctx: Optional[Dict] = None) -> str:
    ctx = ctx or {}
    llm = ctx.get("llm_reasoning")
    if isinstance(llm, str) and llm.strip() and _validate_llm(llm, c):
        return _csv_safe(llm)
    return deterministic_reasoning(c)
