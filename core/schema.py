"""Safe schema accessors + sentinel handling for candidate records.

Design rules (from the spec):
- `-1` sentinels (`github_activity_score`, `offer_acceptance_rate`) mean "no data".
  They are mapped to a NEUTRAL value and a `*_is_present` bit is emitted. They must
  NEVER lower a candidate's score.
- All accessors are total: missing/None/wrong-type inputs return a safe default,
  never raise. This keeps the streaming rank path robust to dirty rows.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

# Sentinel value meaning "no data" for these two signals only.
SENTINEL = -1

# Today, used for recency/age math. Frozen so artifacts are deterministic.
NOW = datetime.datetime(2026, 6, 27)

_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y")


def parse_date(s: Any) -> Optional[datetime.datetime]:
    if not s or not isinstance(s, str):
        return None
    for n in (10, 7, 4):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.datetime.strptime(s[:n], fmt)
            except ValueError:
                pass
    return None


def fnum(x: Any, default: float = 0.0) -> float:
    """Coerce to float; non-numeric / None -> default."""
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    return default


def inum(x: Any, default: int = 0) -> int:
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, float)):
        return int(x)
    return default


def fbool(x: Any) -> bool:
    return bool(x) is True


def lower(x: Any) -> str:
    return (x or "").lower() if isinstance(x, str) else ""


# ---------- top-level sections ----------

def profile(c: Dict[str, Any]) -> Dict[str, Any]:
    p = c.get("profile")
    return p if isinstance(p, dict) else {}


def signals(c: Dict[str, Any]) -> Dict[str, Any]:
    s = c.get("redrob_signals")
    return s if isinstance(s, dict) else {}


def career(c: Dict[str, Any]) -> List[Dict[str, Any]]:
    ch = c.get("career_history")
    return ch if isinstance(ch, list) else []


def education(c: Dict[str, Any]) -> List[Dict[str, Any]]:
    e = c.get("education")
    return e if isinstance(e, list) else []


def skills(c: Dict[str, Any]) -> List[Dict[str, Any]]:
    s = c.get("skills")
    return s if isinstance(s, list) else []


def candidate_id(c: Dict[str, Any]) -> str:
    return c.get("candidate_id") or ""


# ---------- profile convenience ----------

def current_title(c: Dict[str, Any]) -> str:
    return lower(profile(c).get("current_title"))


def current_industry(c: Dict[str, Any]) -> str:
    return lower(profile(c).get("current_industry"))


def country(c: Dict[str, Any]) -> str:
    return lower(profile(c).get("country"))


def years_of_experience(c: Dict[str, Any]) -> float:
    return fnum(profile(c).get("years_of_experience"), 0.0)


# ---------- sentinel-aware signal accessors ----------

class SignalValue:
    """A signal value with an explicit presence bit. `value` is the neutral-mapped
    number safe to use in math; `present` is True iff the source was real data."""

    __slots__ = ("value", "present")

    def __init__(self, value: float, present: bool):
        self.value = value
        self.present = present

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"SignalValue(value={self.value}, present={self.present})"


def sentinel_signal(c: Dict[str, Any], key: str, neutral: float) -> SignalValue:
    """Read a signal that uses -1 as a 'no data' sentinel.

    Returns SignalValue(neutral, present=False) when the value is the -1 sentinel
    OR missing/non-numeric; otherwise the real value with present=True.
    """
    raw = signals(c).get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return SignalValue(neutral, False)
    if raw == SENTINEL:
        return SignalValue(neutral, False)
    return SignalValue(float(raw), True)


def github_activity(c: Dict[str, Any]) -> SignalValue:
    # neutral = 0 contribution; present only when >=0.
    return sentinel_signal(c, "github_activity_score", neutral=0.0)


def offer_acceptance(c: Dict[str, Any]) -> SignalValue:
    return sentinel_signal(c, "offer_acceptance_rate", neutral=0.0)


def recruiter_response_rate(c: Dict[str, Any]) -> Optional[float]:
    """0..1 fraction, or None if missing. This field is NOT a -1-sentinel field."""
    raw = signals(c).get("recruiter_response_rate")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw)


def last_active(c: Dict[str, Any]) -> Optional[datetime.datetime]:
    return parse_date(signals(c).get("last_active_date"))


def open_to_work(c: Dict[str, Any]) -> bool:
    return fbool(signals(c).get("open_to_work_flag"))


def notice_period_days(c: Dict[str, Any]) -> Optional[int]:
    raw = signals(c).get("notice_period_days")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return int(raw)


def salary_range(c: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    s = signals(c).get("expected_salary_range_inr_lpa")
    if not isinstance(s, dict):
        return None, None
    mn, mx = s.get("min"), s.get("max")
    mn = float(mn) if isinstance(mn, (int, float)) and not isinstance(mn, bool) else None
    mx = float(mx) if isinstance(mx, (int, float)) and not isinstance(mx, bool) else None
    return mn, mx


def skill_assessment_scores(c: Dict[str, Any]) -> Dict[str, float]:
    s = signals(c).get("skill_assessment_scores")
    if not isinstance(s, dict):
        return {}
    return {k: fnum(v) for k, v in s.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
