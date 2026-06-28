"""ATLAS judge sandbox server (Hugging Face Docker Space, port 7860).

Serves:
  - the prebuilt static ATLAS UI (spaces/static/) + the frozen artifacts,
  - the 100-line real stratified sample and rank.py for inspection,
  - POST /reproduce  ->  shells the REAL graded command:
        python rank.py --candidates data/sample_candidates.jsonl --out /tmp/submission.csv
    with the subprocess's network namespace neutralised (no proxy env, blocked sockets
    via netguard), a wall-clock timer, then runs validate_submission.py on the output and
    streams stdout + the produced CSV back. This is the SAME code that writes the
    submission — zero-friction reproduction, no cloud account needed.

This is the submitted sandbox_link.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
SAMPLE = APP_ROOT / "data" / "sample_candidates.jsonl"
ARTIFACTS = APP_ROOT / "artifacts"
OUT = Path("/tmp/submission_sandbox.csv")

app = FastAPI(title="ATLAS Sandbox", docs_url="/api/docs")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "sample_present": SAMPLE.is_file(),
        "artifacts_present": ARTIFACTS.is_dir(),
        "rank_py": (APP_ROOT / "rank.py").is_file(),
    }


@app.post("/reproduce")
def reproduce() -> JSONResponse:
    """Run the real rank.py on the 100-line sample, offline, and validate the output."""
    if not SAMPLE.is_file():
        return JSONResponse({"ok": False, "error": "sample missing"}, status_code=500)

    # Deterministic + offline env. Strip every proxy var so the subprocess has no route
    # out, and enable the runtime socket guard via PYTHONSTARTUP-style preimport.
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                             "http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    }
    env.update(
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PYTHONHASHSEED="0",
        PYTHONPATH=str(APP_ROOT),
    )

    # Preimport netguard so any accidental socket use raises inside the ranker.
    code = (
        "import scripts.netguard as ng; ng.enable();"
        "import runpy,sys;"
        f"sys.argv=['rank.py','--candidates',{str(SAMPLE)!r},'--out',{str(OUT)!r},"
        f"'--artifacts',{str(ARTIFACTS)!r}];"
        "runpy.run_path('rank.py', run_name='__main__')"
    )

    t0 = time.time()
    rank = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(APP_ROOT), env=env, capture_output=True, text=True, timeout=300,
    )
    dt = time.time() - t0

    result = {
        "ok": rank.returncode == 0 and OUT.is_file(),
        "wall_clock_s": round(dt, 2),
        "command": "python rank.py --candidates data/sample_candidates.jsonl "
                   "--out submission.csv --artifacts artifacts  (network-guarded)",
        "rank_returncode": rank.returncode,
        "rank_stdout": rank.stdout[-4000:],
        "rank_stderr": rank.stderr[-2000:],
    }

    if OUT.is_file():
        csv_text = OUT.read_text(encoding="utf-8")
        result["csv_head"] = "\n".join(csv_text.splitlines()[:11])
        val = subprocess.run(
            [sys.executable, "validate_submission.py", str(OUT)],
            cwd=str(APP_ROOT), env=env, capture_output=True, text=True, timeout=60,
        )
        result["validator_returncode"] = val.returncode
        result["validator_output"] = (val.stdout + val.stderr).strip()

    return JSONResponse(result)


@app.get("/submission.csv")
def submission() -> FileResponse:
    return FileResponse(str(OUT)) if OUT.is_file() else JSONResponse(
        {"error": "run /reproduce first"}, status_code=404
    )


# Static UI + artifacts last so it does not shadow the API routes above.
if (APP_ROOT / "artifacts").is_dir():
    app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS)), name="artifacts")
STATIC = ROOT / "static"
if STATIC.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
