# Architecture — five diagrams

ATLAS is three planes joined by frozen artifacts. The diagrams below render natively on
GitHub. For the prose methodology see [`blueprint.md`](blueprint.md).

---

## 1. Three-plane system map

The one inviolable rule — no network / GPU / LLM on the graded path — is the red-bordered
Plane B.

```mermaid
flowchart TB
  DATA[(candidates.jsonl<br/>465MB · 100K lines)]
  JD[/Senior AI Engineer JD/]

  subgraph A["PLANE A — OFFLINE PRE-COMPUTE  (network + GPU + API allowed · regenerable)"]
    direction TB
    A1[build_features<br/>D-feature matrix]
    A2["embed<br/>NVIDIA nv-embedqa-e5-v5 1024d<br/>(BGE / TF-IDF no-key fallback)"]
    A3[fit_lexical<br/>BM25 + TFIDF/SVD]
    A4[make_labels<br/>proxy tier 0-5]
    A5{{first_pass fuse<br/>SHORTLIST K=1200<br/>recall gate}}
    A6["llm_rerank<br/>meta/llama-3.3-70b<br/>full shortlist"]
    A7[train_ltr<br/>monotone trees]
    A8[build_honeypots<br/>CLEAN 201 exclude]
    A9[build_reasoning<br/>fact-validated]
    A1 --> A5
    A2 --> A5
    A3 --> A5
    A4 --> A5
    A5 --> A6 --> A7
    A8 --> A7
    A7 --> A9
  end

  subgraph FROZE["FROZEN ARTIFACTS  (committed / LFS · MANIFEST sha256)"]
    ART[(cand_emb · cand_features · bm25<br/>llm_scores · ltr/calibration<br/>honeypot_excludes · reasoning · jd_clause_emb)]
  end

  subgraph B["PLANE B — GRADED rank.py  NO network · NO GPU · NO LLM · 87.9s · 2.25GB · CPU"]
    direction TB
    B1[load artifacts] --> B2[stream JSONL<br/>live signals + id map]
    B2 --> B3[dense + bm25 + rule + llm_fit fuse]
    B3 --> B4[LTR / blend margin]
    B4 --> B5[behavioral × 0.80-1.12]
    B5 --> B6[honeypot GATE + survivor re-verify]
    B6 --> B7[top-100 sort -score, id asc]
    B7 --> B8[attach frozen reasoning] --> B9[self-validate] --> CSV[(submission.csv)]
  end

  subgraph C["PLANE C — LIVE ATLAS  (network + live AI · OFF graded path)"]
    direction TB
    WEB[Next.js cinematic UI<br/>cinema · board · cards · co-pilot]
    SBX["/sandbox runs REAL rank.py<br/>--network none + timer"]
  end

  DATA --> A1 & A2 & A3 & A4 & B2
  JD --> A2 & A4
  A1 --> ART
  A9 --> ART
  ART --> B1
  ART --> WEB
  CSV --> WEB
  B -.same code path.-> SBX

  classDef gated fill:#0D1424,stroke:#FF5C6C,stroke-width:3px,color:#E6EAF2;
  class B gated;
```

---

## 2. Data / artifact flow

Each Plane-A script writes a declared artifact; `rank.py` consumes them; `MANIFEST.json`
records sha256 + producer + size for every one.

```mermaid
flowchart LR
  IN[(candidates.jsonl)]

  subgraph PA["PLANE A producers"]
    direction TB
    P1[build_features.py] --> F1[cand_features.f16.npy]
    P2[embed.py] --> F2[cand_emb.f16.npy] & F3[jd_clause_emb.npz]
    P3[fit_lexical.py] --> F4[bm25.npz] & F5[cand_svd32.f16.npy] & F6[tfidf_svd.pkl] & F7[lexical_cos_jd.f16.npy]
    P4[make_labels.py] --> F8[proxy_tiers.npy]
    P5[first_pass_shortlist.py] --> F9[shortlist.json]
    P6[llm_rerank.py] --> F10[llm_scores.parquet]
    P7[train_ltr.py] --> F11[ltr_model.json] & F12[calibration.json]
    P8[build_honeypots.py] --> F13[honeypot_excludes.json]
    P9[build_reasoning.py] --> F14[reasoning.jsonl]
  end

  MAN[(MANIFEST.json<br/>sha256 · producer · size)]
  F1 & F2 & F3 & F4 & F5 & F6 & F7 & F8 & F9 & F10 & F11 & F12 & F13 & F14 --> MAN

  subgraph PB["PLANE B consumer"]
    RANK[rank.py] --> SUB[(submission.csv)]
  end

  subgraph WEB["build_web_artifacts.py (same code as CSV writer)"]
    W1[ranked_top100.json] & W2[funnel.json] & W3[rejected_traps.json] & W4[intent.json]
  end

  IN --> P1 & P2 & P3 & P4 & RANK
  MAN --> RANK
  RANK --> W1 & W2 & W3 & W4
```

---

## 3. rank.py runtime path

The graded step: load, stream, fuse, gate, sort, attach, validate, write. No network, no
GPU, no LLM — measured 87.9 s / 2.25 GB on the full 100K.

```mermaid
flowchart TB
  S0([start · OMP_NUM_THREADS=1 · PYTHONHASHSEED=0]) --> S1[load frozen artifacts<br/>mmap cand_emb · features · bm25 · llm_scores · honeypot set]
  S1 --> S2[stream candidates.jsonl line-by-line<br/>live signals + id row map]
  S2 --> S3[compute sub-scores per row<br/>S_dense · S_bm25 · S_rule · S_llm]
  S3 --> S4{shortlisted id?}
  S4 -- yes --> S5[base_fit_SL = 0.50 S_llm + 0.20 dense + 0.18 rule + 0.12 bm25]
  S4 -- no --> S6[base_fit_LT = 0.85 x of 0.50 rule + 0.30 dense + 0.20 bm25]
  S5 --> S7[margin = blend or frozen LTR trees]
  S6 --> S7
  S7 --> S8[x anti_trap_multiplier<br/>role_skill_mismatch x0.15 · services x0.55]
  S8 --> S9[x behavioral_multiplier 0.80-1.12<br/>sentinels contribute 0]
  S9 --> S10{honeypot gate<br/>id in clean-201 OR fails re-verify?}
  S10 -- yes --> S11[final = -inf]
  S10 -- no --> S12[final = score]
  S11 --> S13[sort key -final, candidate_id asc]
  S12 --> S13
  S13 --> S14[take top 100 · ranks 1-100 · clamp score non-increasing]
  S14 --> S15[attach frozen reasoning · CSV-sanitize]
  S15 --> S16[in-process validate_submission.py]
  S16 -- valid --> OUT[(write submission.csv)]
  S16 -- invalid --> ERR([refuse to write · exit 1])

  classDef gate fill:#1a0d12,stroke:#FF5C6C,stroke-width:2px,color:#E6EAF2;
  class S10,S11 gate;
```

---

## 4. Honeypot defense layers

Defense-in-depth, all deterministic, with the two critical non-checks called out.

```mermaid
flowchart TB
  IN[candidate stream] --> L1

  subgraph L1["Layer 1 — frozen hard-exclude gate"]
    direction TB
    G1[id in honeypot_excludes.json<br/>clean 201 union] --> GX[final = -inf]
  end

  subgraph SIG["clean structural-impossibility signatures 201 ids"]
    direction LR
    T1[too_many_experts 167]
    T2[career_sum_exceeds_yoe 24]
    T3[expert_zero_duration 21]
    T4[tenure_exceeds_company_age 3]
    T5[career_span_exceeds_yoe 3]
    T6[chronology guards 0 today]
  end
  SIG -.builds.-> G1

  L1 --> L2
  subgraph L2["Layer 2 — live re-verify of top-300 survivors"]
    R1[re-run clean checks pure-python] --> R2{trips >=1 signature?}
    R2 -- yes --> RX[gate to -inf]
    R2 -- no --> RP[keep]
  end

  L2 --> L3
  subgraph L3["Layer 3 — top-10 paranoia"]
    P1{zero signatures AND >=1 real evidence hit?} -- no --> PSWAP[swap for next qualifier]
    P1 -- yes --> POK[confirm slot]
  end

  L3 --> RESULT[0 honeypots in top-100 · 0 in top-10]

  subgraph NEVER["NEVER flagged — critical non-checks"]
    direction TB
    N1[salary inversion min gt max · 18.9% · DATASET NORM]
    N2[-1 sentinels github/offer_acceptance · no data]
    N3[skill_dur_exceeds_career 9231 + edu_order 4715<br/>DEMOTED to soft features]
  end

  classDef bad fill:#1a0d12,stroke:#FF5C6C,stroke-width:2px,color:#E6EAF2;
  classDef safe fill:#0d1a14,stroke:#5BE0E6,stroke-width:2px,color:#E6EAF2;
  class GX,RX,PSWAP bad;
  class NEVER,N1,N2,N3 safe;
```

---

## 5. The funnel

100,000 → shortlist 1,226 → LLM-judged full shortlist → top 100 → top 10, with the trap
burn in the middle.

```mermaid
flowchart TB
  A[100,000 candidates<br/>full pool] --> B
  B[first_pass fuse<br/>0.30 dense + 0.25 bm25 + 0.45 rule]
  B --> C[minus 201 clean honeypots burned<br/>0 will reach top-100]
  C --> D[SHORTLIST 1,226<br/>K=1200 + 905 AI-titled + 845 strong-evidence<br/>recall gate PASS: T5 100% · T4 100%]
  D --> E[LLM re-rank FULL shortlist<br/>meta/llama-3.3-70b · 1,226 real judgments]
  E --> F[blend fusion · anti-trap caps · behavioral × · gate]
  F --> G[TOP 100<br/>validator: valid · 0 honeypots]
  G --> H[TOP 10<br/>all genuine ranking/search/recsys engineers]

  classDef pool fill:#0D1424,stroke:#5B6B8C,color:#E6EAF2;
  classDef burn fill:#1a0d12,stroke:#FF5C6C,color:#E6EAF2;
  classDef win fill:#1a160d,stroke:#F5C04E,color:#E6EAF2;
  class A,B pool;
  class C burn;
  class G,H win;
```
