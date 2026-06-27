"""Salary inversion (min > max) is the 18.9% dataset NORM. It must NEVER be a
honeypot signal. Structural impossibilities still flag correctly."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import honeypot  # noqa: E402
from tests import fixtures  # noqa: E402


def test_salary_inversion_is_detectable_but_not_a_honeypot():
    c = fixtures.salary_inverted_candidate()
    # The inversion is real...
    assert honeypot.salary_inverted(c) is True
    # ...but it is NOT a clean structural signature and does NOT hard-gate.
    assert honeypot.clean_signatures(c) == set()
    assert honeypot.is_honeypot(c) is False


def test_salary_inversion_not_in_signature_lists():
    for sig in honeypot.CLEAN_SIGNATURES + honeypot.SOFT_SIGNATURES:
        assert "salary" not in sig


def test_clean_candidate_not_flagged():
    assert honeypot.is_honeypot(fixtures.base_candidate()) is False


def test_too_many_experts_flagged():
    c = fixtures.too_many_experts_candidate()
    assert "too_many_experts" in honeypot.clean_signatures(c)
    assert honeypot.is_honeypot(c) is True


def test_expert_zero_duration_flagged():
    c = fixtures.expert_zero_duration_candidate()
    assert "expert_zero_duration" in honeypot.clean_signatures(c)
    assert honeypot.is_honeypot(c) is True


def test_keyword_stuffer_is_not_a_structural_honeypot():
    # A non-eng keyword stuffer is an anti-trap target, NOT a structural impossibility.
    c = fixtures.keyword_stuffer_candidate()
    assert honeypot.is_honeypot(c) is False


def test_noisy_signatures_are_soft_not_clean():
    for sig in ("skill_duration_exceeds_career", "edu_degree_order_impossible"):
        assert sig in honeypot.SOFT_SIGNATURES
        assert sig not in honeypot.CLEAN_SIGNATURES
