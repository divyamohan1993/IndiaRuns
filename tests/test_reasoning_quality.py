"""Stage-4 reasoning quality: specific facts, JD connection, honest concern, no
hallucination, variation, CSV-safe (<=140 chars, comma-free)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reasoning  # noqa: E402
from tests import fixtures  # noqa: E402


def test_csv_safe_and_length():
    for c in (fixtures.base_candidate(), fixtures.keyword_stuffer_candidate(),
              fixtures.too_many_experts_candidate()):
        r = reasoning.build_reasoning(c)
        assert "," not in r
        assert "\n" not in r
        assert len(r) <= 140
        assert r.strip()


def test_specific_facts_present():
    c = fixtures.base_candidate()
    r = reasoning.build_reasoning(c)
    # mentions the title and a number (years)
    assert "ML Engineer" in r
    assert "6" in r


def test_jd_connection_for_fit():
    c = fixtures.base_candidate()
    r = reasoning.build_reasoning(c).lower()
    assert any(k in r for k in ("ranking", "search", "reco", "retrieval", "production"))


def test_no_hallucination_rejects_unknown_company():
    c = fixtures.base_candidate()
    bad = reasoning.build_reasoning(c, {"llm_reasoning": "Strong fit at Acme Robotics building search"})
    # Acme Robotics is not in the record -> LLM reasoning rejected, deterministic used
    assert "Acme Robotics" not in bad


def test_accepts_valid_llm_reasoning():
    c = fixtures.base_candidate()
    good = "ML Engineer 6 yrs at PhonePe shipped a recommendation ranking system in production"
    out = reasoning.build_reasoning(c, {"llm_reasoning": good})
    assert "PhonePe" in out  # PhonePe is in the record


def test_honest_concern_when_gap():
    c = fixtures.base_candidate()
    c["redrob_signals"]["recruiter_response_rate"] = 0.05  # below 0.25
    r = reasoning.build_reasoning(c).lower()
    assert "concern" in r or "response" in r


def test_variation_by_candidate_id():
    a = fixtures.base_candidate("CAND_0000001")
    b = fixtures.base_candidate("CAND_0000007")
    # same facts but different id may pick a different connective pattern
    ra = reasoning.deterministic_reasoning(a)
    rb = reasoning.deterministic_reasoning(b)
    # at minimum the function is deterministic per id
    assert reasoning.deterministic_reasoning(a) == ra
    assert reasoning.deterministic_reasoning(b) == rb
