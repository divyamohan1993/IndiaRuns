# Results — Plane A full pre-compute over the real 100,000 candidates

All numbers below are measured on the real `candidates.jsonl` (100,000 lines,
`CAND_0000001..CAND_0100000`), produced by the shipped `precompute/*` scripts and
consumed by `rank.py`. Determinism env: `PYTHONHASHSEED=0`, single-thread BLAS at rank
time. The graded `rank.py` runs CPU-only, no network.

## Frozen artifacts (full pool)

| Artifact | Shape / size | Producer |
|---|---|---|
| `cand_features.f16.npy` | 100000 × 40 (Groups A–E) | build_features.py |
| `cand_emb.f16.npy` | 100000 × 384 (L2-normalized) | embed.py |
| `cand_svd32.f16.npy` | 100000 × 32 | fit_lexical.py |
| `bm25.npz` | 100000 (BM25 vs curated JD terms, [0,1]) | fit_lexical.py |
| `lexical_cos_jd.f16.npy` | 100000 | fit_lexical.py |
| `tfidf_svd.pkl` | pre-fit TfidfVectorizer + TruncatedSVD (self-contained path) | fit_lexical.py |
| `jd_clause_emb.npz` | 11 weighted clauses + ideal + role anchor | embed.py |
| `proxy_tiers.npy` | 100000 (tier 0–5) | make_labels.py |
| `honeypot_excludes.json` | 201 clean structural ids | build_honeypots.py |
| `shortlist.json` | 1198 ids + recall report + per-id first_pass | first_pass_shortlist.py |
| `llm_scores.{json,parquet}` | 1198 rows, 299 real LLM judgments | llm_rerank.py |
| `ltr_model.json` / `calibration.json` | feature order + ship decision | train_ltr.py |
| `reasoning.jsonl` | 1198 lines, 294 LLM-written + fact-validated | build_reasoning.py |
| `MANIFEST.json` | sha256 + size + producer for 18 artifacts (all verified) | core/artifacts.py |

**Embedding backend:** `tfidf-svd-fallback` (spec §11.2). The BGE local-model path is
fully built and primary by default; in this environment the model download/runtime was
not reliable, so the deterministic TF-IDF/SVD dense signal was frozen instead — a real,
valid, honeypot-clean ranking, exactly the documented degradation floor. The NVIDIA
nv-embedqa path is shipped (`nvidia_client.py`) and selected automatically when a key
is present.

## Proxy tier distribution (internal relevance label, never ground truth)

| Tier | Count | Meaning |
|---|---|---|
| 0 | 43,961 | honeypot / non-eng keyword-stuffer |
| 1 | 25,035 | tangential / CV-without-NLP |
| 2 | 5,978 | generic / services-capped |
| 3 | 24,110 | relevant engineer, weak AI evidence |
| 4 | 216 | AI title OR ranking/retrieval **described** evidence + eng title |
| 5 | 700 | described ranking/search/reco at a product company, in-band, active |

Evidence is matched in career **descriptions**, not the skills array — a profile that
merely *lists* "recommendation systems" as a skill earns no fit credit (spec §4.1). This
makes Tier-5 a genuine 700-candidate needle (0.7% of the pool).

## Shortlist + recall gate (spec §2.4)

- K = 1200, shortlist size = **1198** (after force-includes − 201 honeypots).
- Force-included: 905 AI-titled + 845 strong-evidence (`evid_ranking_search_reco ≥ 2`).
- **Recall gate PASS:** proxy-Tier-5 **100.0 %** (700/700), proxy-Tier-4 **100.0 %**
  (216/216) land inside the shortlist.

## Honeypot exclude set (spec §3, clean structural union ONLY)

**201 candidate ids**, regenerated from the clean signatures (no `ge1`/`ge2`):

| Signature | Count |
|---|---|
| too_many_experts | 167 |
| career_sum_exceeds_yoe | 24 |
| expert_zero_duration | 21 |
| tenure_exceeds_company_age | 3 |
| career_span_exceeds_yoe | 3 |

Salary inversion (18.9 % of the pool) is **never** included. The two noisy signatures
(`skill_duration_exceeds_career` 9,231, `edu_degree_order_impossible` 4,715) are demoted
to soft features. Symmetric-difference vs the probe's clean set = 0.

## LLM re-rank (offline, `claude -p` backend)

- Backend `claude_cli` (temperature 0, JSON output, dedup-by-hash, concurrency 6,
  resumable checkpoint, `--max-calls 350`).
- Targeted the **top 300** of the shortlist by `first_pass`; **299 real LLM judgments**
  obtained (1 unparseable → deterministic). Wall ≈ 27 min.
- The LLM was appropriately critical (top genuine fits scored 79–84, keyword-stuffers
  5–18) and emitted disqualifier flags on 292/299 rows.

## Fusion: LTR vs blend (spec §2.6, ship-the-safer-one)

- 5-fold CV-NDCG@10: **blend = 1.0000**, LTR = 0.7660.
- Blend's top-10 mean proxy tier (5.00) ≥ LTR's (5.00); LTR does not clear the margin,
  so we **ship the BLEND**. The monotone-constrained LTR feature pipeline is fully built
  and round-trips to numpy trees; it simply does not beat the blend on this proxy.

## Final submission (`rank.py` over the full 100K)

- `submission.csv`: 100 rows, validator says **"Submission is valid."**
- rank.py wall-clock **≈ 73 s** (≪ 5 min cap), CPU-only, no network.
- **0 honeypots in top-100, 0 in top-10.**
- **Top-10 are all 10 highest real LLM judgments**; 16 of the top-100 carry a real LLM
  score (the rest are long-tail-vetted under the 0.85 ceiling so no un-vetted id outranks
  an LLM-vetted one). Top picks are genuine ranking/search/recsys engineers at product
  companies (LinkedIn-scale RAG ranking, PharmEasy search L2R, CRED LTR, Flipkart RAG,
  Dream11/Ola rankers).

## Total Plane A wall-clock (this run)

build_features 40 s · fit_lexical 69 s · embed (SVD) 6 s · make_labels 21 s ·
build_honeypots 12 s · first_pass_shortlist 68 s · llm_rerank ≈ 27 min ·
train_ltr 30 s · build_reasoning ≈ 17 min. Deterministic stages ≈ 4 min; LLM stages
≈ 44 min; **end-to-end ≈ 48 min** offline.

---

## Verification — graded `rank.py` proof on the real full pool

Every number below was measured by re-running the graded path on the real 100,000-line
`candidates.jsonl` with `OMP_NUM_THREADS=1 PYTHONHASHSEED=0`.

### Budget (hard requirement: ≤ 5 min, ≤ 16 GB)

Measured with `/usr/bin/time -v python rank.py --candidates candidates.jsonl --out submission.csv`:

| Metric | Measured | Budget | Margin |
|---|---|---|---|
| Wall-clock | **1:13.48 (73.5 s)** | 300 s | 4.1× headroom |
| User CPU time | 71.97 s | — | — |
| Peak RSS | **2,107,064 KB ≈ 2.01 GB** | 16 GB | 8× headroom |
| Exit status | 0 | — | — |

### Validator (vendored `validate_submission.py`)

```
$ python validate_submission.py submission.csv
Submission is valid.    (exit 0)
```
100 data rows, header `candidate_id,rank,score,reasoning`, ranks 1–100 unique bare ints,
score non-increasing, ties candidate_id-ascending.

### Honeypot gate (`scripts/assert_no_honeypots.py`, full pool)

```
ranked=100 frozen_set=201 honeypots_in_top100=0 in_top10=0
OK: 0 honeypots in top-100.    (exit 0)
```
Cross-checks the frozen clean-201 set AND a live re-run of the clean structural checks
over the ranked ids. **0 honeypots in top-100, 0 in top-10.** No non-eng-title
keyword-stuffer (Marketing/HR/Sales/etc.) appears anywhere in the top-50 — all top-50
titles are AI/ML/eng (Search/Recommendation/ML/AI/Data Scientist).

### Determinism (byte-identical across runs)

Two independent full runs + the committed file all hash identically:
```
694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f  run_a.csv
694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f  run_b.csv
694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f  submission.csv
```
**Byte-identical: YES.** Single-thread BLAS + `PYTHONHASHSEED=0` + a stable explicit
`(-final, candidate_id)` sort key + frozen artifact bytes remove all nondeterminism.

### No-network / CPU proof (Docker `--network none`)

`docker/Dockerfile.sandbox` (extends `Dockerfile.ranker`) bakes the 100-line stratified
real sample + the sample-sized frozen artifacts. Run with the network namespace removed:
```
$ docker run --rm --network none --cpus=4 --memory=16g -v "$PWD/out:/out" indiaruns-sandbox
wrote /out/submission.csv (100 rows) — self-validation passed.   (exit 0)
$ python validate_submission.py out/submission.csv
Submission is valid.
```
The container succeeds with **no network reachable at all**. Additionally
`tests/test_no_network.py` passes: (a) the rank path imports no networked/heavy-ML libs
(torch/transformers/httpx/requests/xgboost/openai), and (b) running the full pipeline
in-process with `socket.socket`/`create_connection` monkeypatched to raise makes **zero**
socket calls. (Build-time pip uses the network; rank-time does not — the boundary the
spec requires.)

### Internal NDCG vs the naive keyword-count baseline (synthetic proxy, NOT truth)

Scored against the `proxy_tiers` synthetic relevance vector over 100K (relevance gain =
tier 0–5; relevant for MAP/P@k = tier ≥ 3). This is a **relative** sanity check that our
ranker beats the deliberately-wrong `sample_submission` instinct — it is **not** ground
truth (our ranker is partly built from the same proxy signal, so its absolute 1.0 is
expected and not a quality claim).

| Ranking | NDCG@10 | NDCG@50 | MAP | P@10 | **Composite** |
|---|---|---|---|---|---|
| **ATLAS submission** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **1.0000** |
| naive keyword-count baseline | 0.0716 | 0.0761 | 0.3232 | 0.2000 | **0.1171** |
| **Lift** | | | | | **+0.8829 (+753.9 %)** |

Composite weighting = `0.50·NDCG@10 + 0.30·NDCG@50 + 0.15·MAP + 0.05·P@10`.
Top-100 tier≥3: ATLAS 100 vs baseline 30. Top-10 tier≥4: ATLAS 10 vs baseline 0. The
keyword baseline ranks non-fits (NDCG@10 = 0.07), confirming the anti-keyword design.

### Web / results artifacts (built from the SAME data as the CSV)

`precompute/build_web_artifacts.py` emits, into `artifacts/` (copied to
`web/public/artifacts/`): `ranked_top100.json` (verified **0 mismatches** vs
`submission.csv` — provably the submission), `funnel.json` (recall funnel + clean-201
honeypot burn list + a deterministic 2D PCA projection of the top-100), `rejected_traps.json`
(per-signature counts + example ids + the salary-inversion "not a trap" note + the
baseline foil), `intent.json` (JD chip cloud), and `results_top.json` (compact API payload).

### Test suite

`python -m pytest` → **39 passed** (validator, determinism, no-network, sentinels,
gate-blocks-honeypots, salary-not-flagged, features-no-skew, reasoning-quality, budget).
