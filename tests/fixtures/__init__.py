"""Synthetic candidate fixtures for honeypot / gate / feature tests."""

from __future__ import annotations

import copy
from typing import Any, Dict


def base_candidate(cid: str = "CAND_0000001") -> Dict[str, Any]:
    """A clean, plausible AI-eng candidate."""
    return {
        "candidate_id": cid,
        "profile": {
            "anonymized_name": "Test Person",
            "headline": "ML Engineer building ranking systems",
            "summary": "Built an end-to-end recommendation ranking system serving users at scale.",
            "location": "Bangalore",
            "country": "India",
            "years_of_experience": 6.0,
            "current_title": "ML Engineer",
            "current_company": "PhonePe",
            "current_company_size": "1001-5000",
            "current_industry": "Fintech",
        },
        "career_history": [
            {
                "company": "PhonePe", "title": "ML Engineer",
                "start_date": "2021-01-01", "end_date": None, "duration_months": 36,
                "is_current": True, "industry": "Fintech", "company_size": "1001-5000",
                "description": "Built and deployed a production recommendation ranking system "
                               "with embeddings retrieval and NDCG evaluation at scale.",
            },
        ],
        "education": [
            {"institution": "IIT", "degree": "B.Tech", "field_of_study": "CS",
             "start_year": 2013, "end_year": 2017, "grade": "8.5", "tier": "tier_1"},
        ],
        "skills": [
            {"name": "Python", "proficiency": "advanced", "endorsements": 20, "duration_months": 60},
            {"name": "Recommendation Systems", "proficiency": "advanced", "endorsements": 15, "duration_months": 40},
        ],
        "redrob_signals": {
            "profile_completeness_score": 90,
            "signup_date": "2024-01-01",
            "last_active_date": "2026-05-01",
            "open_to_work_flag": True,
            "profile_views_received_30d": 30,
            "applications_submitted_30d": 2,
            "recruiter_response_rate": 0.7,
            "avg_response_time_hours": 4,
            "skill_assessment_scores": {"Python": 85},
            "connection_count": 300,
            "endorsements_received": 50,
            "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 30, "max": 50},
            "preferred_work_mode": "hybrid",
            "willing_to_relocate": True,
            "github_activity_score": 60,
            "search_appearance_30d": 10,
            "saved_by_recruiters_30d": 3,
            "interview_completion_rate": 0.9,
            "offer_acceptance_rate": 0.8,
            "verified_email": True,
            "verified_phone": True,
            "linkedin_connected": True,
        },
    }


def salary_inverted_candidate(cid: str = "CAND_0000002") -> Dict[str, Any]:
    """Clean structurally, but salary min > max (the 18.9% dataset norm)."""
    c = base_candidate(cid)
    c["redrob_signals"]["expected_salary_range_inr_lpa"] = {"min": 50, "max": 30}
    return c


def too_many_experts_candidate(cid: str = "CAND_0000003") -> Dict[str, Any]:
    """Structural honeypot: 6 expert skills."""
    c = base_candidate(cid)
    c["skills"] = [
        {"name": f"Skill{i}", "proficiency": "expert", "endorsements": 5, "duration_months": 24}
        for i in range(6)
    ]
    return c


def expert_zero_duration_candidate(cid: str = "CAND_0000004") -> Dict[str, Any]:
    c = base_candidate(cid)
    c["skills"] = [{"name": "X", "proficiency": "expert", "endorsements": 1, "duration_months": 0}]
    return c


def keyword_stuffer_candidate(cid: str = "CAND_0000005") -> Dict[str, Any]:
    """Non-eng title with stuffed AI skills (a trap, but NOT a structural honeypot)."""
    c = base_candidate(cid)
    c["profile"]["current_title"] = "Marketing Manager"
    c["profile"]["current_industry"] = "Manufacturing"
    c["profile"]["summary"] = "Led marketing campaigns and brand strategy."
    c["career_history"][0]["title"] = "Marketing Manager"
    c["career_history"][0]["description"] = "Ran marketing campaigns and managed brand strategy."
    c["skills"] = [
        {"name": "Information Retrieval", "proficiency": "advanced", "endorsements": 3, "duration_months": 12},
        {"name": "Fine-tuning LLMs", "proficiency": "advanced", "endorsements": 2, "duration_months": 10},
        {"name": "Vector Search", "proficiency": "advanced", "endorsements": 1, "duration_months": 8},
    ]
    return c


def clone(c: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(c)
