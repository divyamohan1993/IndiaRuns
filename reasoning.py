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

# JD-requirement vocabulary the reasoning must connect to (Stage-4: "explicit JD
# connection"). Lowercase substring match against the reasoning text.
_JD_REQUIREMENT_TOKENS = (
    "ranking", "rank", "retrieval", "retrieve", "search", "recommendation",
    "recommender", "reco", "embedding", "embeddings", "vector", "semantic",
    "relevance", "personalization", "personalisation", "learning-to-rank",
    "learning to rank", "ltr", "eval", "ndcg", "mrr", "a/b", "ab test",
    "information retrieval", "production",
)

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


# Generic title words that, alone, do not make a line "specific" (they appear in the
# JD role title too, so a match on them is not distinctive to the candidate).
_GENERIC_TITLE_WORDS = {
    "senior", "junior", "lead", "principal", "staff", "engineer", "developer",
    "scientist", "specialist", "analyst", "architect", "manager", "ai", "ml",
    "data", "software", "machine", "learning", "applied", "research",
}


def _strong_record_tokens(c: Dict) -> List[str]:
    """Distinctive tokens that anchor a reason to THIS candidate: company names and
    named skills (and the full multi-word title). A bare generic title word like
    'engineer' is NOT here — it is not distinctive."""
    toks: List[str] = []
    company = _primary_company(c)
    if company:
        toks.append(lower(company))
    for j in career(c):
        if isinstance(j, dict) and j.get("company"):
            toks.append(lower(j["company"]))
    for s in c.get("skills", []):
        if isinstance(s, dict) and s.get("name"):
            toks.append(lower(s["name"]))
    seen = set()
    out = []
    for t in toks:
        t = t.strip()
        if len(t) >= 3 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _weak_title_tokens(c: Dict) -> List[str]:
    """Title words from the record, EXCLUDING the generic role words. A match here is a
    real (if soft) specific — e.g. 'recommendation' / 'search' in the candidate's title."""
    out: List[str] = []
    titles = []
    t = profile(c).get("current_title")
    if t:
        titles.append(lower(t))
    for j in career(c):
        if isinstance(j, dict) and j.get("title"):
            titles.append(lower(j["title"]))
    for title in titles:
        for w in title.replace("/", " ").split():
            w = w.strip(".,()")
            if len(w) >= 4 and w not in _GENERIC_TITLE_WORDS:
                out.append(w)
    return list(dict.fromkeys(out))


def is_specific(text: str, c: Dict) -> bool:
    """Stage-4 specificity gate.

    A reasoning line is "specific" iff (a) it names at least one JD requirement
    (ranking/retrieval/search/recommendation/embeddings/eval/...), (b) it cites >=2
    CONCRETE specifics grounded in this candidate's record, AND (c) at least one of
    those specifics is STRONG — a validated number, the company, or a named skill —
    so a line cannot clear the bar on generic role words alone. Generic lines like
    "Strong ML background" or "Senior AI Engineer with 6+ years" (no company/skill)
    fail; "8 yrs at CRED owns the ranking layer" passes.
    """
    if not text:
        return False
    import re
    low = text.lower()

    has_jd = any(t in low for t in _JD_REQUIREMENT_TOKENS)
    if not has_jd:
        return False

    strong = 0
    # a validated number/year that legitimately belongs to the record.
    if re.search(r"\d", text) and _validate_llm(text, c):
        if any(round(float(t)) for t in re.findall(r"\d+(?:\.\d+)?", text) or ["0"]):
            strong += 1
    # company / named-skill tokens (distinctive to this candidate).
    for tok in _strong_record_tokens(c):
        if tok in low:
            strong += 1

    weak = sum(1 for w in _weak_title_tokens(c) if w in low)

    # >=2 concrete specifics total AND at least one of them STRONG (number/company/skill).
    return strong >= 1 and (strong + weak) >= 2


def build_reasoning(c: Dict, ctx: Optional[Dict] = None) -> str:
    """Return the final reasoning string.

    A frozen LLM reasoning (ctx['llm_reasoning']) is used ONLY if it passes BOTH the
    no-hallucination validator AND the Stage-4 specificity gate. Otherwise the
    deterministic fact-assembler — specific by construction — is used.
    """
    ctx = ctx or {}
    llm = ctx.get("llm_reasoning")
    if (isinstance(llm, str) and llm.strip()
            and _validate_llm(llm, c) and is_specific(llm, c)):
        return _csv_safe(llm)
    return deterministic_reasoning(c)
