"""No network on the rank path: (a) importing rank.py and its core deps pulls in NO
networked libraries; (b) running the full rank pipeline in-process with socket creation
monkeypatched to raise makes ZERO socket calls."""

import importlib
import os
import socket
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

FORBIDDEN = ("torch", "transformers", "sentence_transformers", "httpx", "requests",
             "urllib3", "openai", "xgboost")


def test_rank_modules_have_no_networked_imports():
    # Import the Plane-B modules; none may import a networked/heavy ML lib.
    for mod in ("rank", "features", "reasoning", "core.score", "core.gate",
                "core.gbdt", "core.subscores", "core.honeypot", "core.schema",
                "core.rule_fit", "core.io_jsonl", "core.artifacts", "core.calibrate"):
        importlib.import_module(mod)
    loaded = set(sys.modules)
    leaked = [m for m in FORBIDDEN if m in loaded]
    assert not leaked, f"rank path imported networked libs: {leaked}"


def test_rank_makes_no_socket_calls(tmp_path, monkeypatch):
    sample = os.path.join(REPO, "data", "sample_candidates.jsonl")
    artifacts = os.path.join(REPO, "artifacts_sample")
    out = str(tmp_path / "submission.csv")

    calls = {"n": 0}
    real_socket = socket.socket

    class GuardSocket(real_socket):
        def __init__(self, *a, **k):
            calls["n"] += 1
            raise AssertionError("rank path attempted to create a socket")

    monkeypatch.setattr(socket, "socket", GuardSocket)
    # also block connect at the C level via create_connection
    def _no_conn(*a, **k):
        calls["n"] += 1
        raise AssertionError("rank path attempted a network connection")
    monkeypatch.setattr(socket, "create_connection", _no_conn)

    sys.argv = ["rank.py", "--candidates", sample, "--out", out, "--artifacts", artifacts]
    import rank
    importlib.reload(rank)
    rc = rank.main()
    assert rc == 0
    assert calls["n"] == 0
    assert os.path.exists(out)
