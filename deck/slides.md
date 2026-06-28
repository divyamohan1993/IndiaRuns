# IndiaRuns / ATLAS — Track 1 Slides

> India Runs x Redrob AI — Track 01. All figures measured on the real 100,000-candidate pool, the real validator, and a `--network none` Docker reproduction.

---

## Slide 1 — Title

# ATLAS
### Intelligent Candidate Discovery & Ranking
**India Runs x Redrob AI — Track 01 (Data & AI Challenge)**

Team IndiaRuns

*Retrieval finds the candidates. An LLM judges the few that matter. A monotone-constrained blender fuses the evidence. A structural gate guarantees no trap survives — all frozen offline so the graded step is a 73-second pure-numpy pass.*

---

## Slide 2 — The problem

**Recruiters drown in profiles and still miss the right person.**

- Keyword filters match words, not fit. They rank by skill-count, so a buzzword-stuffed profile beats a quiet specialist who actually shipped the system.
- The cost is two-sided: great candidates stay invisible, and recruiters waste hours on confident-looking non-fits.
- Redrob's bet is an AI brain for hiring that reads a job description and ranks like a great recruiter would — by understanding who fits, not who matched the most strings.

This dataset makes that hard *on purpose.*

---

## Slide 3 — The insight: the dataset is a trap

**20.4% of the 100,000 candidates have an AI/ML skill keyword. Only 1.0% have an AI/ML job title.**

- That 19.4-point gap is overwhelmingly non-AI roles that *stuffed* AI keywords into their skills array.
- The provided `sample_submission.csv` is the deliberately-wrong baseline: it ranks an **HR Manager #1** and a Content Writer in the top four — purely on skill count.
- Planted **honeypots** (impossible-on-the-numbers profiles) sit in the pool. More than 10 in your top-100 is an automatic disqualification.

**The whole challenge is: beat the keyword instinct, and don't step on a landmine.** ATLAS is built to do exactly that.

---

## Slide 4 — Architecture: three planes, one boundary

**A — Offline pre-compute** (network + GPU + APIs allowed): embeddings, BM25/TF-IDF, deterministic features, a recall first-pass to a 1,200 shortlist, an LLM re-rank of that shortlist, a monotone blender, and frozen reasoning. Regenerable by shipped scripts.

**B — Graded ranker `rank.py`** (the only thing judges reproduce): loads frozen artifacts, streams the JSONL, fuses sub-scores, applies the behavioral multiplier and honeypot gate, writes the top-100 CSV. **CPU-only, no network, no GPU, no LLM at rank time.**

**C — Live product ATLAS** (network + live AI allowed): a cinematic web app that reads Plane B's *output* and never invokes it online.

**The one inviolable rule:** no network, GPU, or LLM call ever sits on the graded path. That is the single most defensible point of the whole submission.

---

## Slide 5 — The hybrid funnel

We took the best idea from three competing designs and grafted them into one pipeline:

1. **Recall first-pass** — `0.30*dense + 0.25*bm25 + 0.45*rule` over all 100K, then keep the top 1,200, force-include every AI-titled and strong-evidence candidate, drop the honeypots. **Recall gate passes: 100% of proxy-Tier-5 and 100% of proxy-Tier-4 land in the shortlist.**
2. **LLM re-rank** — judge only the shortlist, where ~80% of the scoring metric lives. 299 real LLM judgments over the top-300; 294 LLM-written, fact-validated reasoning lines.
3. **Blend / LTR fusion** — a monotone-constrained blender fuses LLM fit, dense, BM25, rule and behavioral into one margin. We *ship the safer one*: the fixed-weight blend won 5-fold CV-NDCG@10 1.0000 vs LTR 0.766, so it ships.
4. **Behavioral multiplier** `[0.80, 1.12]` — availability and reachability modulate, never dominate. "No data" sentinels never penalize.
5. **Honeypot hard-gate** — structural impossibilities are excluded to `-inf`, with a live re-verify of survivors.

---

## Slide 6 — Anti-keyword reasoning: evidence over titles

**We rank by what a candidate *did*, written in their own words — not by what they *listed*.**

- We embed the **career narrative** (titles, companies, descriptions), weighting descriptions above the skills array, so keyword-stuffing the skills list cannot move the vector.
- The **career-evidence features** (shipped a ranking/search/recsys system, built embeddings retrieval, designed NDCG/MRR/MAP eval, deployed to production) are read from descriptions, not from the skills array.
- **The role/skill-mismatch cap (x0.15):** a non-engineering current title that lists an AI skill is multiplied down by 0.15. This is the direct counter to the baseline's failure — and it acts as a deterministic floor *under* the LLM, so model optimism can never out-vote a structural disqualifier.

---

## Slide 7 — Honeypot defense

**Three deterministic layers, defense-in-depth.**

- **Clean-201 hard exclude.** We regenerated the exclude set from high-precision structural-impossibility signatures only — `too_many_experts` (167), `career_sum_exceeds_yoe` (24), `expert_zero_duration` (21), `tenure_exceeds_company_age` (3), `career_span_exceeds_yoe` (3) = **exactly 201 ids**. Each is gated to `-inf`.
- **Live re-verify** of every survivor that reaches the top-300, plus **top-10 paranoia** (must show real shipping evidence).
- **The critical non-check:** salary `min > max` fires on **18.9% of the pool — it is a dataset norm, not a trap.** Flagging it would nuke a fifth of the candidates. We deliberately do **not** flag it.

**Result: 0 honeypots in the top-100, 0 in the top-10.**

---

## Slide 8 — Results (measured, real)

| Metric | Result | Cap |
|---|---|---|
| Wall-clock (full 100K) | **73.5 s** | 300 s |
| Peak memory | **2.01 GB** | 16 GB |
| Network / GPU at rank time | **none** | required |
| Validator | **"Submission is valid."** | — |
| Determinism | **byte-identical** (sha256 694f86dd...) | — |
| Honeypots in top-100 / top-10 | **0 / 0** | <=10 to avoid DQ |
| Internal lift vs naive keyword baseline | **~1.00 vs ~0.07 NDCG@10** | — |

**Top-10:** ML Eng @ Genpact AI (LinkedIn RAG ranking, 50M q/mo); Search Eng @ PharmEasy (L2R search); Recsys Eng @ CRED (LTR+RAG eval); ML Eng @ Flipkart (prod RAG, 10M recsys); Recsys Eng @ Zomato; Search Eng @ Saarthi.ai (L2R @ Dream11, FAISS); AI Eng @ Ola; Sr DS @ Amazon; Search Eng @ Meta; Search Eng @ Haptik.

Tier distribution over 100K: T0 43,961 / T1 25,035 / T2 5,978 / T3 24,110 / T4 216 / T5 700.

---

## Slide 9 — The ATLAS product

A cinematic recruiter experience that makes the ranking legible and trustworthy:

- **Ranking cinema** — a real-data particle funnel: 100,000 pool -> 1,198 shortlist -> the 201 traps combust red -> crystallize to the top 100 then top 10. Every burning dot is a real flagged candidate id.
- **Evidence cards** — the verbatim CSV reasoning string, with the candidate's own words highlighted and tagged to the matched job requirement; one honest concern when a gap exists.
- **Honeypot reveal drawer** — "Caught before they could be hired: 201 excluded," grouped by signature, each pairing the seductive surface with the fatal flaw. Salary inversion is shown explicitly as *not* a trap.
- **Recruiter co-pilot** — filter, compare, summarize, draft outreach over the shipped top-100; honest "Live AI / Offline AI" status pill.
- **Shareable shortlist** — read-only cinematic board with an auto OG image and a one-page top-10 PDF export.

---

## Slide 10 — NVIDIA + GCP + LLM, and the compliance boundary

- **NVIDIA (offline, Plane A only):** hosted embeddings and a 70B-class instruct model for the shortlist re-rank and fact-validated reasoning. The full NVIDIA path is built and degrades cleanly with no key.
- **LLM judging:** 299 real judgments over the top-300 shortlist; 294 fact-validated reasoning lines. A local CLI LLM backend and a deterministic fallback are both wired, so the pipeline runs *with or without* any key.
- **GCP (production, Plane C only):** Cloud Run for the API and web, Secret Manager for the key, optional Vertex job for Plane A. Documented and credential-gated — never needed to build, test, or grade.
- **The boundary:** every AI/network call lives in Plane A or C. **Plane B — the graded `rank.py` — makes zero network, GPU, or LLM calls,** proven by a no-socket test and a `--network none` run.

---

## Slide 11 — Reproducibility

**One command, sealed, twice.**

```
docker run --rm --network none --cpus=4 --memory=16g \
  indiaruns-sandbox  ->  /out/submission.csv
```

- Verified: produced a valid CSV offline, **PASS**.
- `python rank.py --candidates candidates.jsonl --out submission.csv` finishes in 73.5 s at 2.01 GB peak RSS, CPU-only.
- Run it twice and byte-diff: **identical** (`PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, frozen artifact bytes tracked by sha256 in the manifest).
- The vendored `validate_submission.py` runs inside `rank.py`, which refuses to write a non-conforming file.

There is nothing to trust on faith — the grader reproduces the exact bytes.

---

## Slide 12 — Business & roadmap

**ATLAS is the hiring brain Redrob is already building toward — 15M+ live jobs, one OS, one login.**

- **Monetization:** per-seat recruiter SaaS; usage-based ranking API for ATS/job boards; premium co-pilot outreach and intelligence; enterprise on-prem for compliance-sensitive hiring.
- **Virality:** shareable shortlists with auto OG images turn every recruiter's result into a "make your own ranking" funnel; the honeypot-reveal drawer is inherently screenshot-worthy.
- **Trust as the moat:** evidence-linked reasoning, an honest AI-status pill, a sealed reproducible ranker, and a structural anti-trap guarantee — exactly the trust hiring decisions require.
- **Redrob fit:** ATLAS plugs straight into the super-app — job matching across 15M+ jobs, hiring intelligence, and the AI app store — on the path to 10-20M monthly Indians.

---

## Slide 13 — Team & contact

**Team IndiaRuns**

Primary contact: Divya Mohan — divyamohan1993@gmail.com

- GitHub: complete, working, reproducible repository.
- Sandbox: a one-click hosted Space that runs the real `rank.py` on screen.
- Submission: a valid, honeypot-clean, fully reasoned top-100 CSV from the real 100,000.

*Build something real. Make hiring smarter.*
