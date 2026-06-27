# IndiaRuns / ATLAS — Intelligent Candidate Discovery & Ranking (Track 1)

A hybrid retrieval → LLM-rerank → monotone-blend → structural-gate funnel that ranks
candidates the way a great recruiter would: by career *evidence*, not stuffed keywords.

## Three planes

| Plane | What | Constraints |
|---|---|---|
| **A — pre-compute** (`precompute/`) | embeddings, lexical fit, labels, shortlist+recall gate, LLM re-rank, monotone LTR, reasoning | network/GPU/APIs allowed; regenerable |
| **B — graded ranker** (`rank.py`, `core/`, `features.py`, `reasoning.py`) | loads frozen artifacts, streams JSONL, fuses, gates, writes top-100 CSV | **CPU-only, ≤5 min, ≤16 GB, ≤5 GB disk, NO network** |
| **C — live product** (`web/`) | cinematic ATLAS UI over Plane-B outputs | network/APIs allowed; off the graded path |

**Inviolable rule:** no network/GPU/LLM call ever sits on the Plane-B rank-time path.

## Quickstart (graded path)

```bash
pip install -r requirements-rank.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
python validate_submission.py ./submission.csv
```

`rank.py` reads only frozen artifacts from `artifacts/`. It self-validates with the
vendored `validate_submission.py` before writing.

## Prove it on the sample (no keys needed)

```bash
make prove   # build sample artifacts (local/fallback) -> rank -> validate -> pytest
```

## Regenerate artifacts (Plane A, optional)

```bash
pip install -r requirements-precompute.txt
python data/prepare_data.py --source /path/to/candidates.jsonl
python precompute/run_all.py --candidates ./candidates.jsonl --artifacts ./artifacts
```

With `NVIDIA_API_KEY` set, Plane A uses nv-embedqa + Nemotron-70B; otherwise it
degrades to local BGE embeddings (or TF-IDF/SVD) + a deterministic/`claude`-CLI brain.
Every degradation level still produces a valid, honeypot-clean submission.

## Honeypot defense

Hard-exclude = the **clean 201-id** structural-impossibility union only
(`too_many_experts`, `career_sum_exceeds_yoe`, `expert_zero_duration`, chronology guards).
Salary inversion (18.9% of the pool — a dataset norm) is **never** a honeypot signal.
The `-1` sentinels (`github_activity_score`, `offer_acceptance_rate`) **never** penalize.

See `docs/` and `DESIGN`-derived `docs/blueprint.md` for the full methodology.
