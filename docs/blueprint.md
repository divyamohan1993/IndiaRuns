# Blueprint — ATLAS full methodology

This is the end-to-end methodology for the IndiaRuns / ATLAS Track-1 submission. Every
number is measured on the real 100,000-line `candidates.jsonl`, the real
`validate_submission.py`, and the frozen artifacts in `artifacts/`. For the diagrams see
[`architecture.md`](architecture.md); for the proof transcript see [`results.md`](results.md).

---

## 1. The problem and the winning thesis

The challenge ranks 100,000 candidate profiles against a Senior AI Engineer JD. The pool
is adversarial by construction: only **998 (1.0%)** of candidates have an AI/ML *title*,
yet **20,381 (20.4%)** list at least one AI/ML *skill*. The 19.4-point gap is the trap
surface — non-engineering roles (Marketing/HR/Sales/Mechanical) that stuffed AI keywords —
and the shipped `sample_submission.csv` is the deliberately-wrong baseline that falls for
it, ranking an HR Manager and a Content Writer #1–#4 on skill count alone.

**Thesis:** *retrieval finds the candidates, an LLM judges the few that matter, a
monotone-constrained blender fuses the evidence, and a structural gate guarantees no trap
survives — all frozen offline so the graded step is a sub-90-second pure-numpy pass.*

ATLAS is a hybrid funnel that grafts the strongest idea from three explored angles: an
embedding-first recall spine, a feature/LTR fusion layer with monotone constraints, and a
two-stage LLM-rerank funnel that spends the LLM only where 80% of the metric lives (the
top of the list). The single inviolable rule — **no network, GPU, or LLM call on the
graded path** — is what makes the design both compliant and defensible.

---

## 2. The three planes

| Plane | Responsibility | Environment |
|---|---|---|
| **A — Offline pre-compute** | embeddings, lexical fit, features, recall first-pass → shortlist, LLM re-rank, monotone LTR / blend, frozen reasoning, web artifacts | network + GPU + APIs allowed; time-unbounded; fully regenerable by `precompute/*` |
| **B — Graded ranker** (`rank.py`) | load frozen artifacts, stream JSONL, fuse, gate, write top-100 CSV, self-validate | CPU-only · ≤5 min · ≤16 GB · no network |
| **C — Live product** (`web/`) | cinematic ATLAS UI over Plane-B *outputs* | network + APIs allowed; off the graded path |

The graded step is the only thing judges reproduce, and it is intentionally tiny: it does
not embed, train, call an API, or open a socket. It loads bytes whose sha256 is recorded
in `artifacts/MANIFEST.json` and does arithmetic.

---

## 3. JD decomposition

The JD is frozen into weighted requirement clauses in `artifacts/jd_meta.json`. They drive
both the dense retrieval and the LLM judge. The dominant clauses:

| # | Clause | Weight |
|---|---|---|
| C1 | Shipped an end-to-end ranking / search / recommendation system to real users at scale at a **product** company | 0.22 |
| C2 | Production embeddings-based retrieval; embedding drift, index refresh, retrieval-quality regression | 0.16 |
| C3 | Vector DBs / hybrid search infra (FAISS, Elasticsearch, Pinecone, Qdrant, Milvus, Weaviate) | 0.12 |
| C4 | Designed ranking eval frameworks: NDCG, MRR, MAP, offline↔online correlation, A/B testing | 0.12 |
| C5 | Applied ML at product (not services) companies; ~4–5 yrs applied ML within 6–8 total | 0.10 |
| C6 | Strong Python + recent production software engineering | 0.08 |
| C7 | LLM judgment: fine-tune vs prompt, LoRA/QLoRA/PEFT, learning-to-rank | 0.06 |
| C8 | Scrappy product engineering: ships a working ranker fast, learns from users | 0.06 |
| C9 | Pre-LLM-era ML production; understood retrieval/ranking before it was fashionable | 0.04 |
| C10 | HR-tech / marketplace product; distributed systems / large-scale inference | 0.02 |
| C11 | OSS / papers / talks — external validation | 0.02 |

Anti-patterns are never embedded as positive targets; they live in the deterministic
gates (§7).

---

## 4. Sub-scores (computed in Plane A, frozen, fused in Plane B)

Every sub-score is normalized to [0, 1].

- **`S_dense`** — per-clause weighted pool of cosines between the candidate vector and the
  weighted JD clauses + ideal anchor, blended 50/50 with its pool-percentile rank
  (backend-scale-robust). The candidate vector embeds the **career narrative** (headline +
  summary + each "title at company (industry): description" + a down-weighted skills
  clause), so keyword-stuffing the skills array cannot move the vector.
- **`S_bm25`** — BM25 (k1=1.2, b=0.75) over the narrative vs a curated JD term set, IDF
  over the pool. A recall net for plain-language strong fits.
- **`S_rule`** — deterministic role-fit from the JD's literal fit logic (the `tier_proxy`
  rules in `core/rule_fit.py`): career-evidence positives minus anti-pattern penalties.
- **`S_llm`** — frozen `llm_fit_score/100` from the shortlist re-rank, defined only for
  shortlisted ids; the highest-fidelity fit estimate, placed exactly where the metric lives.
- **`role_title_cos`** — cosine of candidate title-text vs an AI-engineering anchor. High
  skill/dense cosine + low title cosine = the keyword-stuffer signature.

**Embedding backend in this run.** This submission's embeddings are real
`nvidia/nv-embedqa-e5-v5` (1024-d) vectors over all 100K narratives, produced in offline
pre-compute and frozen. The local-BGE path and the deterministic TF-IDF + TruncatedSVD
floor remain shipped as the no-key fallback chain. `rank.py` is byte-identical regardless of
which backend produced the embeddings — it reads whatever frozen artifact exists, with no
key and no network.

---

## 5. First pass + shortlist (the recall layer)

```
first_pass = 0.30·S_dense + 0.25·S_bm25 + 0.45·S_rule        # meaning leads
shortlist  = top-K by first_pass  (K = 1200)
           ∪ {all AI-titled current_title}                    # force-include
           ∪ {strong career evidence: evid_ranking_search_reco ≥ 2}
           − {honeypot clean-exclude 201}
```

**Recall gate (hard build step, verified).** We run the JD-encoded tier proxy over all
100K and assert that **100% of proxy-Tier-5 and ≥98% of proxy-Tier-4** land inside the
shortlist before freezing. Measured result: **K=1200, shortlist size 1226** (after
force-includes − honeypots), with **905 AI-titled + 845 strong-evidence**
force-included; recall gate **PASS** at **Tier-5 100% (700/700)** and **Tier-4 100%
(216/216)**. This is the empirical recall validation the LLM-rerank angle was missing.

---

## 6. LLM re-rank of the shortlist (the correction layer)

For shortlisted ids, the offline judge is called at `temperature=0` with JSON output and a
**fact-only bundle** (no free-guess), the JD anti-trap framing handed verbatim, and a
disqualifier checklist. It returns `fit_score` (0–100), `tier` (0–5),
`disqualifier_flags`, `evidence`, `concern`, and a ≤140-char comma-free `reasoning` line.

Engineering: dedup by sha256 of the normalized fact bundle (templated bios collapse to one
call), bounded concurrency, token-bucket throttle, exponential backoff, resumable
checkpoint, and a `--max-calls` cap. Backends: NVIDIA hosted `meta/llama-3.3-70b-instruct`
(when `NVIDIA_API_KEY` is set), the `claude` CLI (live offline judge fallback), or a
deterministic fallback.

**This run.** The NVIDIA `meta/llama-3.3-70b-instruct` backend produced **1,226 real LLM
judgments** over the **full shortlist** (`response_format={"type":"json_object"}`,
temperature 0, concurrency 4–8), wall ≈ 45–60 min. The judge was appropriately critical
(genuine fits scored high, keyword-stuffers low) and emitted disqualifier flags. Frozen to
`artifacts/llm_scores.parquet`.

---

## 7. Anti-trap role-fit logic

### 7.1 Beat keyword-counting by construction
- Embed the **narrative**, not the skills list — a Marketing Manager's campaign text
  embeds far from C1 regardless of stuffed skills.
- `role_title_cos` — high skill/dense cosine + low title cosine = the trap signature.
- BM25 and dense both run over **descriptions** — a plain-language strong fit ("built the
  candidate recommendation ranker serving 2M users") wins on real work.

### 7.2 The deterministic feature vector (`features.py`, shared Plane A & B, no skew)
Grouped with monotone signs frozen in `artifacts/feature_meta.json`:
- **A — career evidence** (monotone +): `evid_ranking_search_reco`,
  `evid_embeddings_vectordb`, `evid_eval_framework`, `evid_production_deploy`,
  `evid_built_endto_end` (matched in **descriptions**, not skills).
- **B — role fit** (mixed): `ai_title_flag` (+), `eng_title_flag` (+),
  `non_eng_title_flag` (−), `ai_skill_count` (not monotone — trap axis),
  **`ai_skill_x_non_eng = ai_skill_count × non_eng_title_flag` (monotone −, the
  keyword-stuffer detector)**, `skill_trust`, `jd_facet_coverage`.
- **C — anti-pattern penalties** (monotone −): `services_only_flag` / `services_fraction`,
  `title_chaser_flag`, `cv_speech_robo_no_nlp`, `recent_langchain_only`,
  `pure_research_flag`, `no_external_validation` (sentinel-safe), `out_of_band_yoe`.
- **D — behavioral** (monotone +): `resp_rate_norm`, `recency_score`, `open_to_work_flag`,
  `notice_fit`, `interview_completion_rate`, `availability_composite`.
- **E — honeypot flags** (monotone −): `hp_hard_flag`, `hp_signature_count`,
  `too_many_experts`, plus the two demoted soft signals. Salary inversion is deliberately
  NOT a feature.
- **F — semantic** (monotone +): `emb_cos_*`, `svd_*`, `lexical_cos_jd`.

### 7.3 Multiplicative anti-trap caps (applied to `margin`)
- **`role_skill_mismatch`** (THE trap): non-eng `current_title` AND ≥1 AI skill ⇒
  **×0.15**. The direct counter to the `sample_submission` failure, and a deterministic
  floor the LLM cannot overrule.
- `services_only_career` ⇒ ×0.55 (graded by `services_fraction`; a prior product stint
  removes it); `title_chaser` ⇒ ×0.70; `cv_speech_robotics_without_nlp` ⇒ ×0.50;
  `recent_langchain_only` ⇒ ×0.60; `pure_research_no_prod` ⇒ ×0.50; `non_india_no_relocate`
  ⇒ ×0.85 (soft). `anti_trap_multiplier = Π(applicable caps)`.

---

## 8. Behavioral-signal multiplier

Applied after role-fit, bounded `behavioral_multiplier ∈ [0.80, 1.12]` — it modulates,
never dominates: it can demote an unavailable perfect-on-paper candidate but cannot
promote an unqualified-but-active one past a genuine fit.

Contributions (clipped to the band): recruiter response rate (centered on the pool median
0.44), last-active recency, `open_to_work_flag`, notice period, interview-completion rate,
verified email/phone, recruiter saves / profile views, profile completeness.

**Sentinel rule (hard, unit-tested):** `github_activity_score == -1` (64.6%) and
`offer_acceptance_rate == -1` (59.6%) contribute exactly 0 — flipping either to −1 must
never decrease a candidate's score.

---

## 9. Fusion → final margin (ship-the-safer-one)

Shortlisted candidates (the only ones that realistically reach top-100):
```
base_fit_SL = 0.50·S_llm + 0.20·S_dense + 0.18·S_rule + 0.12·S_bm25
```
Long-tail (safety net over all 100K):
```
base_fit_LT = (0.50·S_rule + 0.30·S_dense + 0.20·S_bm25) · 0.85    # no un-vetted id outranks an LLM-vetted one
```
A monotone-constrained blender (`core/gbdt.py` frozen numpy trees) can turn the assembled
feature vector into the margin, but we keep it **only if it beats the fixed-weight blend on
5-fold proxy CV-NDCG@10**.

**This run.** Blend CV-NDCG@10 = **0.8925** vs LTR = **0.9096**; the LTR's slim edge does
not clear the ship-the-safer-one margin, so we **ship the BLEND** (`use_ltr: false`). The
monotone-constrained LTR pipeline is fully built and round-trips to numpy trees — it is kept
as the documented alternative. Either way,
the feature engineering is the reusable IP and the monotone constraints guarantee the model
can never reward a known anti-pattern.

---

## 10. Final score assembly (Plane B)

```
role'  = margin · anti_trap_multiplier              # §7.3 caps
final  = role'  · behavioral_multiplier             # §8, ∈ [0.80, 1.12]
final  = -inf   if id ∈ honeypot_exclude OR fails live structural re-verify   # §11
score  = round(rescale01(final), 6)
sort key = (-final, candidate_id)                   # equal scores ⇒ id ASC (validator)
take top 100; ranks 1..100
```

The top region is the most conservatively gated: a top-10 slot is reached only if a
candidate is simultaneously high on LLM-judged fit AND dense + lexical role-fit AND passes
every anti-trap gate AND is available AND is not a honeypot. Multiplicative gating
concentrates the strongest signal exactly where NDCG@10 (0.50) + NDCG@50 (0.30) live.

---

## 11. Honeypot defense

Three deterministic layers; full detail in [`honeypot_defense.md`](honeypot_defense.md).
- **Layer 1** — frozen hard-exclude gate: the **clean 201-id** union of structural-
  impossibility signatures (`too_many_experts` 167, `career_sum_exceeds_yoe` 24,
  `expert_zero_duration` 21, `tenure_exceeds_company_age` 3, `career_span_exceeds_yoe` 3).
- **Layer 2** — live re-verify of the top-300 survivors (pure-python, microseconds).
- **Layer 3** — top-10 paranoia (zero signatures + at least one real evidence hit).

Salary inversion (18.9%) is deliberately NOT a trap; the `-1` sentinels never penalize;
the two noisy signatures are demoted to soft features. **Result: 0 honeypots in top-100,
0 in top-10.**

---

## 12. Reasoning generation (Stage-4 quality)

Two sources, both produced offline and frozen; `rank.py` only selects and CSV-sanitizes
(zero network). Tier 1: frozen LLM reasoning (shortlist), ≤140-char, comma-free,
fact-grounded, post-validated so every named skill/company/number appears in the record.
Tier 2: deterministic fact-assembly from the candidate's own strongest features + one
honest concern, with hash-keyed connectives for variation — the reproducible fallback if a
judge regenerates without the LLM cache. **This run:** 294 LLM-written + fact-validated
reasoning lines (`artifacts/reasoning.jsonl`), deterministic for the rest.

---

## 13. Runtime, determinism, budget

- **Time:** load artifacts ~3 s + one streaming JSON pass + numpy cosine matmul (sub-second)
  + frozen-tree eval + fuse/gate/sort ⇒ **87.9 s measured** vs the 300 s cap.
- **RAM:** mmap'd `cand_emb.f16` + small matrices + Python overhead ⇒ **2.25 GB measured**
  vs 16 GB. The 465 MB JSONL is strictly streamed, never fully loaded.
- **Determinism:** `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, frozen artifact bytes, no
  rank-time randomness, stable explicit sort key ⇒ byte-identical
  (`sha256 f39f5fa5…21c60c`). CI runs `rank.py` twice and byte-diffs.
- **No network:** proven three ways — `--network none` Docker, a no-socket monkeypatch
  test, and the absence of any networked import on the rank path.

See [`reproducibility.md`](reproducibility.md) and [`results.md`](results.md) for the full
proof transcript.
