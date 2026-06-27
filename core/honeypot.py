"""Structural honeypot detection — clean impossibility signatures only.

Critical corrections baked in (spec §0.2 / §3):
  - Salary inversion (min > max) is a DATASET NORM (18.9%) and is NEVER checked.
  - `skill_duration_exceeds_career` and `edu_degree_order_impossible` are DEMOTED to
    SOFT signals (returned separately); they never hard-gate a candidate to -inf.
  - The two sentinels are irrelevant here (they are not impossibilities).

`clean_signatures(c)` returns the set of CLEAN structural-impossibility signatures a
candidate trips. A non-empty set => hard-exclude (final = -inf). `soft_signatures(c)`
returns the demoted noisy signals (small negative feature only).

Company-age checks need a pool-wide proxy (earliest observed start per company). For the
streaming rank path we accept an optional precomputed `company_first` map; without it the
company-age signature is simply not evaluated (it contributes 0 of the 201 in most pools).
"""

from __future__ import annotations

from typing import Dict, Optional, Set

from core.schema import NOW, education, parse_date, profile, career, skills

# The clean, high-precision structural-impossibility signatures (hard gate).
CLEAN_SIGNATURES = (
    "too_many_experts",
    "career_sum_exceeds_yoe",
    "expert_zero_duration",
    "tenure_exceeds_company_age",
    "career_span_exceeds_yoe",
    # chronology guards (0 hits in the current pool, kept cheap):
    "edu_end_before_start",
    "career_end_before_start",
    "current_with_enddate",
    "tenure_gt_360",
    "career_start_future",
    "career_end_future",
    "duration_span_mismatch",
)

# Demoted to SOFT — ordinary noise, NOT planted traps (never hard-gate).
SOFT_SIGNATURES = (
    "skill_duration_exceeds_career",
    "edu_degree_order_impossible",
)

TOO_MANY_EXPERTS_THRESHOLD = 5


def _yoe(c: Dict) -> float:
    y = profile(c).get("years_of_experience")
    return float(y) if isinstance(y, (int, float)) and not isinstance(y, bool) else 0.0


def clean_signatures(c: Dict, company_first: Optional[Dict[str, object]] = None) -> Set[str]:
    """Return the set of CLEAN structural-impossibility signatures the candidate trips.

    Salary inversion is intentionally NOT among the checks.
    """
    hits: Set[str] = set()
    y = _yoe(c)

    # --- skills: expert proficiency anomalies ---
    expert_total = 0
    expert_zero = 0
    for s in skills(c):
        if not isinstance(s, dict):
            continue
        if s.get("proficiency") == "expert":
            expert_total += 1
            d = s.get("duration_months")
            if d in (0, None) or (isinstance(d, (int, float)) and d == 0):
                expert_zero += 1
    if expert_zero > 0:
        hits.add("expert_zero_duration")
    if expert_total >= TOO_MANY_EXPERTS_THRESHOLD:
        hits.add("too_many_experts")

    # --- education chronology ---
    for e in education(c):
        if not isinstance(e, dict):
            continue
        sy, ey = e.get("start_year"), e.get("end_year")
        if isinstance(sy, int) and isinstance(ey, int) and ey < sy:
            hits.add("edu_end_before_start")

    # --- career chronology + experience math ---
    sum_dur = 0.0
    earliest = None
    for j in career(c):
        if not isinstance(j, dict):
            continue
        dm = j.get("duration_months")
        sd = parse_date(j.get("start_date"))
        ed = parse_date(j.get("end_date"))
        if isinstance(dm, (int, float)) and not isinstance(dm, bool):
            sum_dur += dm
        if sd and (earliest is None or sd < earliest):
            earliest = sd
        if isinstance(dm, (int, float)) and dm > 0 and sd and ed and ed < sd:
            hits.add("career_end_before_start")
        if j.get("is_current") and j.get("end_date") not in (None, ""):
            hits.add("current_with_enddate")
        if isinstance(dm, (int, float)) and dm > 360:
            hits.add("tenure_gt_360")
        if sd and sd > NOW:
            hits.add("career_start_future")
        if ed and ed > NOW:
            hits.add("career_end_future")
        if sd and ed and isinstance(dm, (int, float)):
            span = (ed - sd).days / 30.44
            if abs(span - dm) > 14:
                hits.add("duration_span_mismatch")
        if company_first is not None:
            comp = (j.get("company") or "").strip().lower()
            if comp and isinstance(dm, (int, float)) and dm > 0:
                cfirst = company_first.get(comp)
                if cfirst is not None:
                    age_m = (NOW - cfirst).days / 30.44  # type: ignore[operator]
                    if dm > age_m + 18:
                        hits.add("tenure_exceeds_company_age")

    if y > 0 and sum_dur > 1.5 * (y * 12):
        hits.add("career_sum_exceeds_yoe")
    if earliest and y > 0:
        span_y = (NOW - earliest).days / 365.25
        if span_y > y + 3:
            hits.add("career_span_exceeds_yoe")

    return hits


def soft_signatures(c: Dict) -> Set[str]:
    """Return the DEMOTED noisy signatures (soft feature only; never a hard gate)."""
    hits: Set[str] = set()
    y = _yoe(c)

    if y > 0:
        for s in skills(c):
            if not isinstance(s, dict):
                continue
            d = s.get("duration_months")
            if isinstance(d, (int, float)) and not isinstance(d, bool) and d > (y * 12) + 12:
                hits.add("skill_duration_exceeds_career")
                break

    # degree ordering: an advanced degree finishing well before a more basic one
    def lvl(d: str) -> int:
        d = d.lower()
        if "phd" in d or "doctor" in d:
            return 3
        if any(k in d for k in ("master", "m.s", "m.tech", "mba", "msc")):
            return 2
        if any(k in d for k in ("bachelor", "b.e", "b.tech", "b.sc", "bsc")):
            return 1
        return 0

    adv = []
    for e in education(c):
        if not isinstance(e, dict):
            continue
        ey = e.get("end_year")
        deg = e.get("degree") or ""
        if isinstance(ey, int) and lvl(deg) > 0:
            adv.append((ey, lvl(deg)))
    for i in range(len(adv)):
        for k in range(len(adv)):
            if adv[i][1] > adv[k][1] and adv[i][0] < adv[k][0] - 1:
                hits.add("edu_degree_order_impossible")
    return hits


def is_honeypot(c: Dict, company_first: Optional[Dict[str, object]] = None) -> bool:
    """True iff the candidate trips >=1 CLEAN structural signature (hard exclude)."""
    return len(clean_signatures(c, company_first=company_first)) > 0


def salary_inverted(c: Dict) -> bool:
    """Helper used ONLY to prove salary inversion is detectable but deliberately
    excluded from honeypot scoring. NEVER call this in the gate."""
    from core.schema import salary_range
    mn, mx = salary_range(c)
    return mn is not None and mx is not None and mn > mx
