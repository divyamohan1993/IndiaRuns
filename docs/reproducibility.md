# Reproducibility

The graded step is deliberately small and boring: one command, no network, no GPU, no
randomness, byte-identical output. Everything below is measured on the real 100,000-line
`candidates.jsonl`.

---

## The single command

```bash
pip install -r requirements-rank.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

This is the exact `reproduce_command` in `submission_metadata.yaml`. `rank.py` reads only
the frozen artifacts in `artifacts/` (whose bytes are checksummed in
`artifacts/MANIFEST.json`), streams the JSONL line-by-line, fuses the sub-scores, applies
the anti-trap caps + behavioral multiplier + honeypot gate, selects the top-100, attaches
the frozen reasoning, runs the vendored validator on its own output, and writes the CSV. It
never downloads, embeds, trains, or opens a socket.

```bash
python validate_submission.py ./submission.csv     # -> "Submission is valid."
```

---

## Determinism

Two independent full runs and the committed file all hash identically:

```
694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f  run_a.csv
694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f  run_b.csv
694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f  submission.csv
```

What removes every source of nondeterminism:
- `PYTHONHASHSEED=0` — stable dict/set iteration.
- `OMP_NUM_THREADS=1` — single-thread BLAS kills float-sum-order nondeterminism in the
  cosine matmul and tree evaluation.
- Frozen artifact bytes — the sha256 of every input is recorded in `MANIFEST.json`.
- No rank-time randomness — no sampling, no seeds that vary.
- A stable explicit sort key `(-final, candidate_id)` — equal scores resolve to
  candidate_id ascending, the only tie order the validator accepts.

CI runs `rank.py` twice and byte-diffs the two CSVs; `tests/test_determinism.py` asserts
the same locally. `reproduce.sh` sets the env vars for you.

---

## No-network / CPU / budget proof

**Budget** (`/usr/bin/time -v python rank.py …`):

| Metric | Measured | Bound | Headroom |
|---|---|---|---|
| Wall-clock | **73.5 s** (1:13.48) | 300 s | 4.1× |
| User CPU time | 71.97 s | — | — |
| Peak RSS | **2.01 GB** (2,107,064 KB) | 16 GB | 8× |
| Exit status | 0 | — | — |

The 465 MB JSONL is strictly streamed line-by-line — never fully loaded. `cand_emb.f16` is
mmap'd. `scripts/timing_harness.sh` + `scripts/check_budget.py` fail the build if wall-clock
≥300 s or peak RSS ≥16 GiB.

**No network — proven three independent ways:**

1. **Namespace removed.** `docker/Dockerfile.sandbox` (extends `Dockerfile.ranker`) bakes
   the 100-line stratified real sample + sample-sized artifacts and runs offline:
   ```
   $ docker run --rm --network none --cpus=4 --memory=16g -v "$PWD/out:/out" indiaruns-sandbox
   wrote /out/submission.csv (100 rows) — self-validation passed.   (exit 0)
   $ python validate_submission.py out/submission.csv
   Submission is valid.
   ```
   The container succeeds with **no network reachable at all**.
2. **No-socket test.** `tests/test_no_network.py` runs the full rank path with
   `socket.socket` / `socket.create_connection` monkeypatched to raise — **zero** socket
   calls are made.
3. **No networked imports.** The same test asserts the rank path imports none of
   `torch`, `transformers`, `httpx`, `requests`, `xgboost`, `openai`. Build-time `pip` uses
   the network; rank-time does not — exactly the boundary the spec requires.

**CPU-only:** `requirements-rank.txt` pins CPU-only numpy + scikit-learn (no torch, no CUDA);
`uses_gpu_for_inference: false` in the metadata is proven by the `--network none` Docker run
on a CPU image.

---

## Artifact manifest

`rank.py` loads only frozen artifacts; `artifacts/MANIFEST.json` records sha256 + producer +
size for every one. The shipped set:

| Artifact | Shape / size | Producer |
|---|---|---|
| `cand_features.f16.npy` | 100000 × 40 | `build_features.py` |
| `cand_emb.f16.npy` | 100000 × 384 (L2-normalized) | `embed.py` |
| `cand_svd32.f16.npy` | 100000 × 32 | `fit_lexical.py` |
| `bm25.npz` | 100000 BM25 scores [0,1] | `fit_lexical.py` |
| `lexical_cos_jd.f16.npy` | 100000 | `fit_lexical.py` |
| `tfidf_svd.pkl` | pre-fit vectorizer + SVD (self-contained path) | `fit_lexical.py` |
| `jd_clause_emb.npz` | 11 weighted clauses + ideal + role anchor | `embed.py` |
| `jd_meta.json` | frozen JD clauses + weights | `embed.py` |
| `proxy_tiers.npy` | 100000 (tier 0–5) | `make_labels.py` |
| `honeypot_excludes.json` | clean 201 structural ids | `build_honeypots.py` |
| `shortlist.json` | 1198 ids + recall report | `first_pass_shortlist.py` |
| `llm_scores.{json,parquet}` | 1198 rows, 299 real LLM judgments | `llm_rerank.py` |
| `ltr_model.json` / `calibration.json` | feature order + ship decision | `train_ltr.py` |
| `feature_meta.json` | feature names + monotone signs + thresholds | `build_features.py` |
| `reasoning.jsonl` | 1198 lines, 294 LLM-written + fact-validated | `build_reasoning.py` |
| `candidate_index.json` | id → row map | `build_features.py` |
| `MANIFEST.json` | sha256 + size + producer for every artifact | `core/artifacts.py` |

The default `rank.py` fast path works from `git clone` + `git lfs pull` with no network and
no Plane-A rerun. To regenerate everything from scratch (Plane A), see the README and
`precompute/run_all.py`.

---

## One-shot proof bundle

```bash
make prove
```

builds the sample artifacts (local/fallback, no keys), runs `rank.py`, validates, and runs
the full `pytest` suite (validator, determinism, no-network, sentinels,
gate-blocks-honeypots, salary-not-flagged, features-no-skew, reasoning-quality, budget).
