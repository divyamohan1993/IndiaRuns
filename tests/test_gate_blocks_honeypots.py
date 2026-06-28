"""The honeypot gate blocks all structural honeypots from the top-100 (and top-10).
Also verifies a flagged candidate gets margin -inf and never reaches the output."""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import gate, honeypot  # noqa: E402
from core.artifacts import load_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_zero_honeypots_in_submission(sample_submission):
    sample = os.path.join(REPO, "data", "sample_candidates.jsonl")
    payload = load_json(os.path.join(REPO, "artifacts_sample", "honeypot_excludes.json"), default={})
    frozen = set(payload.get("clean_exclude", []))
    # live re-detection too
    live = {c["candidate_id"] for c in iter_candidates(sample) if honeypot.is_honeypot(c)}

    with open(sample_submission, newline="", encoding="utf-8") as f:
        ranked = {r["candidate_id"]: int(r["rank"]) for r in csv.DictReader(f)}

    in_top100 = [cid for cid in ranked if cid in frozen or cid in live]
    assert in_top100 == [], f"honeypots in top-100: {in_top100}"


def test_hard_gate_sets_neg_inf():
    assert gate.apply_hard_gate(0.9, "CAND_0000031", {"CAND_0000031"}) == gate.NEG_INF
    assert gate.apply_hard_gate(0.9, "CAND_0000002", {"CAND_0000031"}) == 0.9


def test_role_skill_mismatch_cap():
    # non-eng title + AI skill => x0.15 cap
    det = {"non_eng_title_flag": 1.0, "ai_skill_count": 3.0}
    assert abs(gate.anti_trap_multiplier(det) - 0.15) < 1e-9
    # eng title => no cap
    det2 = {"non_eng_title_flag": 0.0, "ai_skill_count": 3.0}
    assert gate.anti_trap_multiplier(det2) == 1.0


def test_known_honeypot_ids_excluded(sample_submission):
    # CAND_0000031 (AI-titled structural honeypot) must NOT be in the output.
    with open(sample_submission, newline="", encoding="utf-8") as f:
        ids = {r["candidate_id"] for r in csv.DictReader(f)}
    assert "CAND_0000031" not in ids
