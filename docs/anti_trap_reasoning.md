# Anti-trap reasoning — why evidence beats keywords

The hardest part of this challenge is not finding AI engineers; it is *not* being fooled by
people who pasted AI keywords into their skills array. This document explains the trap, the
role-fit logic that defeats it, and the multiplicative caps that make the defeat
un-buyable.

---

## The AI-keyword trap, measured

| Population | Count | % of pool |
|---|---|---|
| Candidates with an AI/ML **title** | 998 | 1.0% |
| Candidates with ≥1 AI/ML **skill** keyword | 20,381 | 20.4% |
| **The gap (skill but no AI title)** | ~19,400 | **19.4 pt** |

That 19.4-point gap is the trap surface. Most candidates who list "Information Retrieval",
"Vector Search", "RAG" or "Fine-tuning LLMs" are not AI engineers — they are Marketing
Managers, HR Managers, Customer Support reps and Mechanical Engineers who stuffed the
keywords in. Real examples from the pool:

- `CAND_0000097` — **Mechanical Engineer**; skills include Information Retrieval, Semantic
  Search, Sentence Transformers, HF Transformers.
- `CAND_0000121` — **Customer Support**; skills include Vector Search, Recommendation
  Systems, RAG, Fine-tuning LLMs.
- `CAND_0000201` — **Marketing Manager**; skills include Information Retrieval, Embeddings,
  Fine-tuning LLMs, HF Transformers.

The shipped `sample_submission.csv` is the deliberately-wrong baseline: it ranks an HR
Manager and a Content Writer #1–#4 purely on AI-skill count. A keyword count cannot tell a
builder from a buzzword. ATLAS inverts that instinct.

---

## Role-fit logic: three structural defenses

### 1. Embed the narrative, not the skills list
The candidate vector is built from the **career narrative** — headline + summary + each
"title at company (industry): description" — with the skills clause down-weighted. A
Marketing Manager's campaign descriptions embed far from the JD's "shipped an end-to-end
ranking system" clause regardless of which skills were stuffed into the array. The vector
encodes what the person *did*, not what they *typed*.

### 2. Read evidence in descriptions, not in skills
Both the dense and BM25 signals, and the Group-A career-evidence features
(`evid_ranking_search_reco`, `evid_embeddings_vectordb`, `evid_eval_framework`,
`evid_production_deploy`, `evid_built_endto_end`), are matched against the **career
descriptions**, not the skills array. A profile that merely *lists* "recommendation
systems" as a skill earns zero fit credit; a profile that *describes* "built the candidate
recommendation ranker serving 2M users" earns it all. This is why proxy-Tier-5 is a genuine
700-candidate needle (0.7% of the pool) rather than the 20,381 that have an AI skill.

### 3. The title-vs-skill mismatch signal
`role_title_cos` is the cosine of the candidate's title text against an AI-engineering
anchor. The keyword-stuffer signature is **high skill/dense cosine + low title cosine** —
strong AI vocabulary attached to a non-engineering role. The detector feature
`ai_skill_x_non_eng = ai_skill_count × non_eng_title_flag` (monotone −) fires precisely on
this population, and roughly 69% of the pool has a non-engineering title, so it is a
high-leverage discriminator.

---

## The ×0.15 cap: making the defeat un-buyable

A soft penalty is not enough — a determined stuffer with many keywords could still
accumulate enough score to climb. The decisive lever is a **multiplicative cap** applied to
the `margin`:

> **`role_skill_mismatch`** — a non-engineering `current_title` paired with ≥1 AI skill ⇒
> **`margin ×= 0.15`.**

Because it is multiplicative, no quantity of keywords can out-buy it: 100 stuffed AI skills
times 0.15 is still 0.15 of a non-fit. It is also the **deterministic floor under the
LLM** — even if the offline judge were optimistic about a stuffer, the floor wins. The full
cap set:

| Cap | Trigger | Multiplier |
|---|---|---|
| `role_skill_mismatch` (THE trap) | non-eng title + ≥1 AI skill | **×0.15** |
| `services_only_career` | every stint at a services firm, no product stint | ×0.55 (graded by `services_fraction`; a prior product stint removes it) |
| `title_chaser` | ≥3 stints ≤20 months | ×0.70 |
| `cv_speech_robotics_without_nlp` | CV/speech/robotics with no NLP/IR evidence | ×0.50 |
| `recent_langchain_only` | <3 yrs, LangChain-on-OpenAI only, no pre-LLM IR evidence | ×0.60 |
| `pure_research_no_prod` | research-only, no production shipping | ×0.50 |
| `non_india_no_relocate` | outside India, no relocation signal | ×0.85 (soft) |

`anti_trap_multiplier = Π(applicable caps)`. The thresholds are frozen in
`feature_meta.json`. Crucially, when the fusion uses the monotone-constrained LTR, the
monotone signs guarantee the model can never reward any of these anti-patterns even on
unseen rows — a provable property, not a tuned hope.

---

## Evidence > title (the principle, stated)

The proxy tiers encode the principle directly: a "Data Engineer" who built retrieval can be
Tier-5, while a "Recommendation Systems Engineer" who is structurally impossible is Tier-0.
Title is a weak prior; described, deployed, at-scale work is the signal. This is why the
real top-10 are all genuine ranking/search/recsys engineers (LinkedIn-scale RAG ranking,
PharmEasy search L2R, CRED LTR, Flipkart RAG, Dream11/Ola rankers) and why no
keyword-stuffer reaches the top-50. See [`results.md`](results.md) for the full listing.
