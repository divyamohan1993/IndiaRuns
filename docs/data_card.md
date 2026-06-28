# Data Card — Redrob candidate pool

All numbers measured on the real 100,000-line `candidates.jsonl` (465 MB, IDs
`CAND_0000001`…`CAND_0100000`). Reference copies of the challenge's machine-readable
files live in `docs/refs/` (`candidate_schema.json`, `sample_candidates.json`,
`sample_submission.csv`, `submission_metadata_template.yaml`). The pool file itself is
**never committed** (see `data/README.md`).

## Schema (top-level)
`candidate_id`, `profile`, `career_history[]`, `education[]`, `skills[]`,
`certifications[]`, `languages[]`, `redrob_signals`. See `docs/refs/candidate_schema.json`.

## Pool composition (measured)
- **Titles** are overwhelmingly non-engineering: Business Analyst 5833, HR Manager 5830,
  Mechanical Engineer 5791, Accountant 5764, … The true AI/ML titles total a few hundred
  (ML Engineer 167, AI Research Engineer 153, Data Scientist 145, …).
- **AI title:** only **998 (1.0%)** have an AI/ML-looking title.
- **AI skill keyword:** **20,381 (20.4%)** have ≥1 AI/ML skill. The 19.4-pt gap between
  "has AI skills" and "has AI title" **is the trap surface** — non-AI roles that stuffed
  AI keywords.
- **All-services-firm careers** (TCS/Infosys/Wipro/Accenture/Cognizant/Capgemini/HCL/
  Tech Mahindra/Mindtree/Mphasis): ~8.2k–9.7k → discounted per JD.
- **Industry:** IT Services 29.9k (~30%, the services bucket to discount), Software 22.4k,
  Manufacturing 22.3k, then Fintech / Food Delivery / E-commerce / SaaS / AI-ML / EdTech /
  Gaming — the product-company industries where genuine fits live.
- **Country:** India 75.1%, USA 10.0%, rest spread. No visa sponsorship → non-India capped.
- **Education tier (prestige, NOT relevance):** tier_3 53.2k, tier_4 51.9k, tier_2 27.8k,
  tier_1 6.9k — tier_3/4 dominate, as briefed.
- **YOE percentiles:** p5 1.6, p25 3.9, p50 6.8, p75 9.9, p95 14.0, max 16.9 — most of the
  pool sits in the JD's 5–9 band, so YOE alone discriminates little.
- **recruiter_response_rate percentiles:** p5 0.10, p25 0.25, p50 0.44, p75 0.62, p95 0.76 —
  the multiplier centers on the median 0.44; bottom-quartile (<0.25) is "not reachable".
- **last_active_date:** concentrated 2025-10 → 2026-05; older than ~6 months is down-weighted.

## Sentinels (NEVER penalize)
- `github_activity_score == -1`: **64.6%** ("no GitHub").
- `offer_acceptance_rate == -1`: **59.6%** ("no offer history").
- `open_to_work_flag == True`: **35.3%**.

## Honeypots (corrected — see `docs/honeypot_defense.md`)
- **Salary inversion `min > max`** fires on **18,865 (18.9%)** → a **DATASET NORM**,
  never a honeypot signal.
- **Clean structural-impossibility union = exactly 201 candidate_ids** (the hard exclude):
  `too_many_experts` (167), `career_sum_exceeds_yoe` (24), `expert_zero_duration` (21),
  `tenure_exceeds_company_age` (3), `career_span_exceeds_yoe` (3), plus 0-hit chronology guards.
- **DEMOTED to soft** (ordinary noise, NOT planted traps): `skill_duration_exceeds_career`
  (9,231) and `edu_degree_order_impossible` (4,715).

## Baseline foil
`docs/refs/sample_submission.csv` is the deliberately **wrong** baseline — it ranks an HR
Manager and a Content Writer #1–#4 by AI-skill count. Our ranker must invert that instinct.

## Trap surface (the central data fact)
The pool is adversarial: **998 (1.0%)** have an AI/ML title but **20,381 (20.4%)** list ≥1
AI/ML skill. That 19.4-point gap is overwhelmingly non-AI roles that stuffed AI keywords —
the exact trap the JD warns about and the `sample_submission` falls for. ATLAS defeats it
by embedding the career narrative (not skills) and reading evidence in descriptions (not the
skills array). See `docs/anti_trap_reasoning.md`.

## Internal relevance proxy
There are no labels. We synthesize a JD-encoded Tier 0–5 proxy (`precompute/make_labels.py`,
ported from the probe's `tier_proxy.py`) for **internal NDCG estimation only** — never as
truth. Distribution over 100K: **T0** 43,961 · **T1** 25,035 · **T2** 5,978 · **T3** 24,110
· **T4** 216 · **T5** 700 — Tier-5 is a genuine 0.7% needle.
