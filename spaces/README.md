---
title: ATLAS Candidate Ranking Sandbox
emoji: 🛰️
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# ATLAS — Judge Sandbox (Hugging Face Docker Space)

This is the submitted **`sandbox_link`** for IndiaRuns Track 1 / ATLAS. It is a
zero-friction, one-click reproduction harness: no cloud account, no API key, no local
setup. Open the Space and press **"Run rank.py on the 100-sample"** to execute the
**real graded ranker** with the network disabled and watch the wall-clock timer, the
emitted `submission.csv`, and the vendored validator's verdict.

## What it does

The container bakes:

- `rank.py` + `core/` + `features.py` + `reasoning.py` — the exact Plane-B graded code,
- the matching **sample-sized frozen artifacts** (`artifacts_sample/`),
- the **100-line real, stratified** sample (`data/sample_candidates.jsonl`: fits + traps + typical),
- the vendored `validate_submission.py`,
- a small FastAPI server (`spaces/server.py`) that serves a static ATLAS UI + the
  artifacts and exposes `POST /reproduce`.

`POST /reproduce` runs:

```
python rank.py --candidates data/sample_candidates.jsonl --out submission.csv --artifacts artifacts
```

with every proxy env var stripped and `scripts/netguard.py` enabled (sockets raise on
use), then runs `validate_submission.py` on the output. This is the **same code path**
that produced the committed `submission.csv` — the UI is provably the submission.

## One-click deploy

### Option A — Hugging Face Spaces (recommended; this is the submitted link)

1. Create a new Space: **New → Space → SDK: Docker → Blank**.
2. Push this repository's contents (the Space build context is the repo root, because the
   Dockerfile copies `rank.py`, `core/`, `artifacts_sample/`, `data/`, and `spaces/`).
   Easiest path: keep `spaces/Dockerfile` as the Space's `Dockerfile` at the build root,
   or set the Space to build from the repo with `dockerfile_path: spaces/Dockerfile`.
3. The Space boots on port **7860** (declared in this README's `app_port`). No secrets
   are required to build or run.

### Option B — Run locally (identical image)

```bash
docker build -f spaces/Dockerfile -t atlas-space .
docker run --rm -p 7860:7860 atlas-space
# open http://localhost:7860
```

## Endpoints

| Method | Path             | Purpose                                              |
|--------|------------------|------------------------------------------------------|
| GET    | `/`              | Static ATLAS UI (top-10, traps, Reproduce button).   |
| GET    | `/api/health`    | Liveness + which assets are present.                  |
| POST   | `/reproduce`     | Run the real `rank.py` offline + validate.           |
| GET    | `/submission.csv`| The CSV produced by the last `/reproduce`.           |
| GET    | `/artifacts/...` | The frozen JSON artifacts (read-only).               |

## Why a HF Space and not Cloud Run for the judge link

A Docker Space needs no GCP project, billing account, or credentials from the judge — it
is genuinely one click. The production deployment (Cloud Run, `asia-south1`) is documented
separately in `infra/README.md`; it is credential-gated and never required to evaluate.
