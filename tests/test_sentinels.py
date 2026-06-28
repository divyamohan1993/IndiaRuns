"""Sentinel handling: -1 means 'no data' and must map to a neutral value with a
present=False bit. Flipping a real value to -1 must NEVER increase the neutral-mapped
contribution beyond 0 (i.e. never penalize)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import schema  # noqa: E402


def _cand(github=50, offer=0.8):
    return {
        "candidate_id": "CAND_0000001",
        "profile": {"current_title": "ML Engineer", "years_of_experience": 6.0},
        "redrob_signals": {
            "github_activity_score": github,
            "offer_acceptance_rate": offer,
            "open_to_work_flag": True,
        },
    }


def test_github_sentinel_neutral():
    present = schema.github_activity(_cand(github=80))
    absent = schema.github_activity(_cand(github=-1))
    assert present.present is True and present.value == 80.0
    assert absent.present is False and absent.value == 0.0


def test_offer_sentinel_neutral():
    present = schema.offer_acceptance(_cand(offer=0.9))
    absent = schema.offer_acceptance(_cand(offer=-1))
    assert present.present is True and present.value == 0.9
    assert absent.present is False and absent.value == 0.0


def test_sentinel_never_negative():
    # The neutral value is 0; a -1 sentinel must map to 0, never to -1 (a penalty).
    for key, fn in (("github_activity_score", schema.github_activity),
                    ("offer_acceptance_rate", schema.offer_acceptance)):
        c = {"redrob_signals": {key: -1}}
        sv = fn(c)
        assert sv.value == 0.0
        assert sv.present is False


def test_missing_signal_is_absent_neutral():
    c = {"redrob_signals": {}}
    assert schema.github_activity(c).value == 0.0
    assert schema.github_activity(c).present is False
    assert schema.offer_acceptance(c).present is False


def test_accessors_are_total():
    # Garbage input must not raise.
    assert schema.years_of_experience({}) == 0.0
    assert schema.current_title({}) == ""
    assert schema.recruiter_response_rate({"redrob_signals": {"recruiter_response_rate": "x"}}) is None
    assert schema.salary_range({}) == (None, None)
    assert schema.career({"career_history": None}) == []
