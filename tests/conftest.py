"""Shared test fixtures: paths to the committed sample + its frozen artifacts, and a
helper to run rank.py end-to-end on the sample."""

import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(REPO, "data", "sample_candidates.jsonl")
ARTIFACTS = os.path.join(REPO, "artifacts_sample")


@pytest.fixture(scope="session")
def repo():
    return REPO


@pytest.fixture(scope="session")
def sample_path():
    return SAMPLE


@pytest.fixture(scope="session")
def artifacts_dir():
    return ARTIFACTS


def run_rank(out_path, extra_env=None, mode="fast"):
    env = dict(os.environ)
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("PYTHONHASHSEED", "0")
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, os.path.join(REPO, "rank.py"),
           "--candidates", SAMPLE, "--out", out_path,
           "--artifacts", ARTIFACTS, "--mode", mode]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


@pytest.fixture(scope="session")
def sample_submission(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("rank") / "submission.csv")
    res = run_rank(out)
    assert res.returncode == 0, f"rank.py failed:\n{res.stdout}\n{res.stderr}"
    return out
