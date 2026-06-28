# Interview prep — Stage-5 defend-your-work Q&A

A candid set of the hard questions a judge will ask, with the answer grounded in the real
verified numbers. The posture throughout: be specific, cite the measurement, and never
claim more than the data supports.

---

### Q1. Why is there no network on the rank path? Isn't the LLM your best signal?

The LLM **is** the best signal — which is exactly why it runs offline in Plane A and is
**frozen into an artifact**, not called at rank time. The grading constraint is ≤5 min,
≤16 GB, CPU-only, no network; a rank-time API call would be slow, non-deterministic, and a
Stage-3 DQ risk. So we spend the LLM where 80% of the metric lives (the top of the
shortlist), freeze its judgments to `llm_scores.parquet`, and `rank.py` just reads them.
The graded step is a pure-numpy pass: **73.5 s, 2.01 GB**, and **byte-identical**
(`sha256 694f86dd…cc457f`) across runs. We prove no-network three ways — `--network none`
Docker, a no-socket monkeypatch test, and the absence of any networked import on the path.
This is also the cleanest possible answer here: the LLM improves quality but is never a
dependency; the pipeline produces a valid, honeypot-clean submission with **no key at all**.

### Q2. Why ship the fixed-weight blend instead of the learning-to-rank model?

Ship-the-safer-one, decided empirically. We trained the monotone-constrained LTR and held
it to a bar: keep it only if it beats the fixed-weight blend on 5-fold proxy CV-NDCG@10. It
didn't — blend = **1.0000** vs LTR = **0.7660** on this proxy — so we ship the blend. The
LTR pipeline is fully built and round-trips to numpy trees; we just don't deploy a model
that loses to a simpler, more transparent baseline. Two honest caveats I'd volunteer: (a)
the proxy is synthetic and partly shares signal with our own ranker, so the absolute 1.0 is
not a quality claim — it's a *relative* check that we beat the keyword baseline; (b) the LTR
remains the reusable IP, and its monotone constraints are a *provable* guarantee that the
model can never reward a known anti-pattern, which is why we kept it in the repo.

### Q3. Why exclude 201 candidates when only ~80 honeypots were planted?

Because the cost asymmetry is extreme. Including one honeypot in the top-100 risks the
">10 in top-100" DQ; excluding a few extra genuine-but-odd profiles costs negligible recall
(they're non-fits anyway). The 201 is **not** an arbitrary inflation — it's the exact
deduplicated union of the *clean structural-impossibility* signatures: `too_many_experts`
167, `career_sum_exceeds_yoe` 24, `expert_zero_duration` 21, `tenure_exceeds_company_age` 3,
`career_span_exceeds_yoe` 3. The core cluster is unmistakable: `expert` proficiency is
0.137% of all skills and 99,800 candidates have zero experts, yet 167 claim 5–12 experts
each. I'd also flag the correction I'm proud of: an earlier "≥1 signature" set was polluted
by two *noisy* signatures (`skill_duration_exceeds_career` 9,231,
`edu_degree_order_impossible` 4,715) that fire on ordinary data; we demoted those to soft
features so they never hard-gate. And we deliberately do **not** flag salary inversion
(`min>max`, 18.9%) — that's a dataset norm; flagging it would nuke a fifth of the pool.

### Q4. How does the reasoning avoid hallucination?

Two sources, both offline and frozen; `rank.py` only selects and CSV-sanitizes. The LLM
tier writes ≤140-char, comma-free reasons from a **fact-only bundle** (the candidate's own
parsed facts, with an explicit "use only facts provided; no invented skills/companies"
instruction) and is then **post-validated**: every named skill, company, and number must
appear in the candidate's record, else we fall back to the deterministic assembler. The
deterministic tier builds the reason purely from the candidate's strongest features plus one
honest concern, with hash-keyed connectives for variation. So both tiers draw only from the
JSON, and the LLM tier has a fact-validation gate on top. This run produced 294 LLM-written
+ fact-validated lines; the rest are deterministic. Every reason is also rank-consistent in
tone and matches the sample's 62–84-char style.

### Q5. Walk me through the latency/quality tradeoff.

We split the work by where it pays off. Embeddings, BM25 fit, feature extraction, the
recall first-pass, the LLM re-rank, LTR training, and reasoning all happen in **Plane A**
(time-unbounded, network/GPU allowed) and are frozen. The shortlist is the lever: K=1200
plus force-includes gives us a **measured 100% recall on proxy-Tier-5 and Tier-4** before
freezing, so the expensive LLM only judges the ~300 that can realistically reach the top.
At rank time, **Plane B** does only arithmetic over frozen artifacts — fuse, cap, multiply,
gate, sort — in 73.5 s. The quality lives in Plane A; the speed and determinism live in
Plane B; the shortlist recall gate is what lets us spend the LLM budget without sacrificing
recall. If I had more time I'd push the LLM judge across the full shortlist (1198) rather
than the top 300, and re-run the LTR-vs-blend bake-off on those richer labels.

### Q6. Your internal NDCG is 1.00 — isn't that suspicious?

Yes, and I'd call it out before you do. It's NDCG against a **synthetic** proxy
(`proxy_tiers`) that our ranker is partly built from, so 1.00 is *expected* and is **not** a
ground-truth quality claim. We report it only as a *relative* sanity check: the same proxy
scores the naive keyword-count baseline at NDCG@10 ≈ 0.07, confirming the anti-keyword
design works and that the deliberately-wrong `sample_submission` instinct is exactly
backwards. The real evidence of quality is qualitative: the top-10 are all genuine
ranking/search/recsys engineers at product companies, and no keyword-stuffer reaches the
top-50.

### Q7. What if the hidden grading pool differs from the 100K you tuned on?

Three robustness layers cover this. (1) The honeypot gate's **Layer 2** re-runs the clean
structural checks live on the top-300 survivors, so a trap in a reordered pool is still
caught even if it wasn't in the frozen 201. (2) The anti-trap caps are **multiplicative and
deterministic** — they fire on structure (non-eng title + AI skill), not on memorized ids.
(3) The fusion's monotone constraints (in the LTR path) guarantee no anti-pattern is ever
rewarded on unseen rows. The chronology guards (`*_future`, `edu_end_before_start`, etc.)
hit 0 in this pool but are kept precisely because the hidden pool may differ.

### Q8. What are the weakest parts of the submission?

Honestly: (a) the dense signal in this environment fell back to TF-IDF/SVD because the
embedding model download wasn't reliable here — the BGE and NVIDIA paths are shipped and
auto-selected when available, but this run's dense term is lexical, not neural; (b) the LLM
judged the top 300, not the full 1198, so the long-tail relies on the rule+dense+bm25 blend
under a 0.85 ceiling; (c) the internal metric is a proxy, not truth. None of these threaten
validity, honeypot-safety, or the budget — they're quality ceilings I'd lift with a key and
more compute, not correctness bugs.

---

### One-line summaries to have ready

- **Compliance:** 73.5 s, 2.01 GB, CPU-only, byte-identical, no network — proven three ways.
- **Anti-trap:** embed the narrative not the skills; evidence in descriptions not the array;
  `role_skill_mismatch ×0.15` makes the trap un-buyable.
- **Honeypots:** clean-201 hard gate + live re-verify + top-10 paranoia ⇒ 0/0; salary
  inversion and `-1` sentinels deliberately never penalize.
- **Fusion:** ship-the-safer-one — blend beat LTR on CV-NDCG, so we ship the blend.
- **Reasoning:** offline, fact-validated, deterministic fallback ⇒ no hallucination.
