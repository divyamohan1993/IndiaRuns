"""Budget sanity on the sample: rank.py finishes well within time and peak RAM stays
modest. (Full-pool budget is enforced by scripts/check_budget.py + the Docker harness;
this guards against gross regressions in CI.)"""

import resource
import time

from tests.conftest import run_rank


def test_runs_fast_on_sample(tmp_path):
    out = str(tmp_path / "submission.csv")
    t0 = time.time()
    res = run_rank(out)
    dt = time.time() - t0
    assert res.returncode == 0, res.stderr
    # the 160-line sample must rank in a few seconds; generous CI bound
    assert dt < 60, f"rank.py on sample took {dt:.1f}s"


def test_peak_rss_reasonable(tmp_path):
    out = str(tmp_path / "submission.csv")
    res = run_rank(out)
    assert res.returncode == 0
    # in-process peak RSS of the test runner stays well under the 16 GB cap
    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KB on Linux
    assert peak_kb < 4_000_000, f"peak RSS {peak_kb} KB"
