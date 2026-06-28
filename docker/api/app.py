"""ATLAS Plane-C API (FastAPI).

Serves the frozen Plane-B output artifacts (the same JSON the submission was built
from) and proxies live LLM requests with a graceful backend chain:

    nvidia  ->  claude-cli  ->  deterministic

The backend is selected at *runtime* from the environment. NO key is required to
build this image, and NO key is required for the server to start and serve every
read-only artifact endpoint. The live endpoints (/api/intent, /api/copilot,
/api/outreach, /api/compare) degrade to a deterministic, fact-grounded brain when
no key / CLI is present, so the product is fully functional offline.

This service NEVER invokes rank.py and is never on the graded path.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Artifacts directory: mounted/copied at deploy time. Defaults to the repo layout.
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "/app/artifacts"))

app = FastAPI(title="ATLAS API", version="1.0.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- artifacts
@lru_cache(maxsize=64)
def _load_artifact(name: str) -> Any:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    path = ARTIFACTS_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"artifact not found: {safe}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------------ LLM backends
def _strip_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _nvidia_available() -> bool:
    return bool(os.environ.get("NVIDIA_API_KEY"))


def _claude_cli_available() -> bool:
    return bool(shutil.which("claude"))


def backend_name() -> str:
    forced = (os.environ.get("LLM_BACKEND") or "auto").lower()
    if forced in ("nvidia", "claude_cli", "deterministic"):
        if forced == "nvidia" and not _nvidia_available():
            return "deterministic"
        if forced == "claude_cli" and not _claude_cli_available():
            return "deterministic"
        return forced
    if _nvidia_available():
        return "nvidia"
    if _claude_cli_available():
        return "claude_cli"
    return "deterministic"


def _chat_nvidia(system: str, user: str) -> Optional[dict]:
    import httpx  # lazy; only when a key is present

    base = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model = os.environ.get("NVIDIA_CHAT_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
    headers = {
        "Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        r = httpx.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return _strip_json(content)
    except Exception:
        return None


def _chat_claude_cli(system: str, user: str) -> Optional[dict]:
    claude = shutil.which("claude")
    if not claude:
        return None
    prompt = f"{system}\n\n{user}\n\nRespond with ONLY a single JSON object, no prose, no code fences."
    try:
        res = subprocess.run([claude, "-p", prompt], capture_output=True, text=True, timeout=120)
        return _strip_json(res.stdout)
    except Exception:
        return None


def chat_json(system: str, user: str) -> tuple[dict, str]:
    """Returns (json, backend_used). Falls through nvidia -> claude_cli -> {} (deterministic)."""
    name = backend_name()
    if name == "nvidia":
        out = _chat_nvidia(system, user)
        if out is not None:
            return out, "nvidia"
    if name in ("nvidia", "claude_cli"):
        out = _chat_claude_cli(system, user)
        if out is not None:
            return out, "claude_cli"
    return {}, "deterministic"


# ----------------------------------------------------------------------------- schemas
class IntentReq(BaseModel):
    jd: str


class CopilotReq(BaseModel):
    message: str
    context: Optional[List[Dict[str, Any]]] = None


class OutreachReq(BaseModel):
    candidate_id: str


class CompareReq(BaseModel):
    candidate_ids: List[str]


# --------------------------------------------------------------------------- endpoints
@app.get("/api/health")
@app.get("/healthz")
def health() -> Dict[str, Any]:
    arts = []
    if ARTIFACTS_DIR.is_dir():
        arts = sorted(p.name for p in ARTIFACTS_DIR.glob("*.json"))
    return {
        "status": "ok",
        "llm_backend": backend_name(),
        "nvidia_key_present": _nvidia_available(),
        "claude_cli_present": _claude_cli_available(),
        "artifacts_dir": str(ARTIFACTS_DIR),
        "artifacts": arts,
    }


@app.get("/api/results")
def results() -> Any:
    return _load_artifact("results_top.json")


@app.get("/api/ranked")
def ranked() -> Any:
    return _load_artifact("ranked_top100.json")


@app.get("/api/funnel")
def funnel() -> Any:
    return _load_artifact("funnel.json")


@app.get("/api/rejected")
def rejected() -> Any:
    return _load_artifact("rejected_traps.json")


@app.get("/api/intent")
def intent_default() -> Any:
    # The frozen, shipped intent decomposition (always available, offline-safe).
    return _load_artifact("intent.json")


@app.get("/api/candidate/{candidate_id}")
def candidate(candidate_id: str) -> Any:
    data = _load_artifact("results_top.json")
    for c in data.get("candidates", []):
        if c.get("candidate_id") == candidate_id:
            return c
    raise HTTPException(status_code=404, detail="candidate not in top-100")


def _candidates_by_id(ids: List[str]) -> List[Dict[str, Any]]:
    data = _load_artifact("results_top.json")
    by = {c["candidate_id"]: c for c in data.get("candidates", [])}
    return [by[i] for i in ids if i in by]


@app.post("/api/intent")
def intent(req: IntentReq) -> JSONResponse:
    system = (
        "You decompose a job description into weighted hiring requirement chips. "
        "Output JSON: {\"must_haves\":[{\"label\":str}],\"anti_patterns\":[{\"label\":str}],"
        "\"behavioral\":[{\"label\":str}]}. Only facts from the JD."
    )
    out, used = chat_json(system, req.jd[:6000])
    if not out:
        out = _load_artifact("intent.json")  # deterministic shipped fallback
    return JSONResponse({"backend": used, "intent": out})


@app.post("/api/copilot")
def copilot(req: CopilotReq) -> JSONResponse:
    ctx = req.context or _load_artifact("results_top.json").get("candidates", [])[:20]
    system = (
        "You are ATLAS Co-Pilot, a recruiting assistant. Answer ONLY from the provided "
        "candidate facts; never invent skills, companies, or numbers. Output JSON: "
        "{\"answer\":str,\"cited_ids\":[str]}."
    )
    user = f"Candidates (facts):\n{json.dumps(ctx)[:8000]}\n\nRecruiter: {req.message[:2000]}"
    out, used = chat_json(system, user)
    if not out:
        # Deterministic grounded fallback: surface the top matches by score.
        top = sorted(ctx, key=lambda c: -float(c.get("score", 0)))[:3]
        answer = "Top matches for your query: " + "; ".join(
            f"{c.get('title','')} @ {c.get('company','')} (rank {c.get('rank')})" for c in top
        )
        out = {"answer": answer, "cited_ids": [c.get("candidate_id") for c in top]}
    return JSONResponse({"backend": used, **out})


@app.post("/api/outreach")
def outreach(req: OutreachReq) -> JSONResponse:
    cand = _candidates_by_id([req.candidate_id])
    if not cand:
        raise HTTPException(status_code=404, detail="candidate not in top-100")
    c = cand[0]
    system = (
        "Write a concise, warm recruiter outreach message (<=90 words). Use ONLY the "
        "provided facts. Output JSON: {\"subject\":str,\"body\":str}."
    )
    out, used = chat_json(system, json.dumps(c))
    if not out:
        out = {
            "subject": f"Senior AI Engineer @ Redrob — your {c.get('title','')} work stood out",
            "body": (
                f"Hi, your work as {c.get('title','')} at {c.get('company','')} "
                f"({c.get('yoe','')} yrs) is a strong match for a Senior AI Engineer role at "
                "Redrob building ranking/search systems. Open to a quick chat this week?"
            ),
        }
    return JSONResponse({"backend": used, **out})


@app.post("/api/compare")
def compare(req: CompareReq) -> JSONResponse:
    cands = _candidates_by_id(req.candidate_ids[:4])
    if not cands:
        raise HTTPException(status_code=404, detail="no matching candidates")
    system = (
        "Compare these candidates for a Senior AI Engineer ranking role. Use ONLY the "
        "provided facts. Output JSON: {\"verdict\":str,\"ranking\":[str]}."
    )
    out, used = chat_json(system, json.dumps(cands))
    if not out:
        ranked_ids = [c["candidate_id"] for c in sorted(cands, key=lambda c: c.get("rank", 999))]
        best = cands[0]
        out = {
            "verdict": (
                f"{best.get('title','')} @ {best.get('company','')} leads on rank "
                f"({best.get('rank')}); ordering reflects the frozen ATLAS score."
            ),
            "ranking": ranked_ids,
        }
    return JSONResponse({"backend": used, **out})
