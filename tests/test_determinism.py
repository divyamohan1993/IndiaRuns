"""rank.py is byte-deterministic: two runs produce identical CSVs."""

import os

from tests.conftest import run_rank


def test_byte_identical(tmp_path):
    out1 = str(tmp_path / "s1.csv")
    out2 = str(tmp_path / "s2.csv")
    r1 = run_rank(out1)
    r2 = run_rank(out2)
    assert r1.returncode == 0 and r2.returncode == 0
    with open(out1, "rb") as a, open(out2, "rb") as b:
        assert a.read() == b.read()


def test_score_column_non_increasing(sample_submission):
    import csv
    with open(sample_submission, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)]
    scores = [float(r["score"]) for r in sorted(rows, key=lambda r: int(r["rank"]))]
    for a, b in zip(scores, scores[1:]):
        assert a >= b
