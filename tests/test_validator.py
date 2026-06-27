"""The produced submission passes the vendored validator and matches the CSV contract."""

import csv
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _validator():
    spec = importlib.util.spec_from_file_location(
        "validate_submission", os.path.join(REPO, "validate_submission.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_submission_valid(sample_submission):
    errors = _validator().validate_submission(sample_submission)
    assert errors == [], "\n".join(errors)


def test_contract_shape(sample_submission):
    with open(sample_submission, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [r for r in reader if any(c.strip() for c in r)]
    assert header == ["candidate_id", "rank", "score", "reasoning"]
    assert len(rows) == 100
    ranks = [int(r[1]) for r in rows]
    assert sorted(ranks) == list(range(1, 101))
    scores = [float(r[2]) for r in rows]
    # non-increasing by rank
    by_rank = sorted(zip(ranks, scores, [r[0] for r in rows]))
    for (r1, s1, c1), (r2, s2, c2) in zip(by_rank, by_rank[1:]):
        assert s1 >= s2
        if s1 == s2:
            assert c1 < c2  # equal scores -> candidate_id ascending


def test_rank_is_bare_int(sample_submission):
    with open(sample_submission, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = row["rank"].strip()
            assert str(int(r)) == r  # no 1.0, no leading zeros, no +
