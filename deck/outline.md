# IndiaRuns / ATLAS — Track 1 Pitch Deck Outline

**India Runs x Redrob AI — Track 01: The Data & AI Challenge (Intelligent Candidate Discovery & Ranking)**

A 13-slide narrative. Every number is measured on the real 100,000-candidate pool, the real `validate_submission.py`, and a `--network none` Docker reproduction. Nothing here is invented.

| # | Slide | One-line purpose |
|---|---|---|
| 1 | Title | IndiaRuns / ATLAS, Track 1, team and thesis in one breath. |
| 2 | The problem | Recruiters miss hidden gems; keyword filters can't see fit. |
| 3 | The insight / the trap | 20.4% have AI skills, only 1.0% have AI titles. The baseline ranks an HR Manager #1 — that is the trap the dataset sets. |
| 4 | Three-plane architecture | Offline pre-compute, a sealed CPU-only graded ranker, and a live product — with one inviolable boundary. |
| 5 | The hybrid funnel | Recall -> LLM rerank -> blend -> behavioral -> honeypot gate. |
| 6 | Anti-keyword reasoning | Evidence beats title; the x0.15 role/skill-mismatch cap. |
| 7 | Honeypot defense | Clean-201 exclude, 0 in top-100, salary-inversion-is-the-norm correction. |
| 8 | Results | 73.5 s / 2.01 GB / CPU / offline, validator valid, byte-identical determinism, top-10, internal lift vs baseline. |
| 9 | The ATLAS product | Ranking cinema, evidence cards, honeypot reveal, recruiter co-pilot, shareable shortlist. |
| 10 | NVIDIA + GCP + LLM usage | Where each runs, and the Plane-B compliance boundary that keeps the graded path clean. |
| 11 | Reproducibility | One command, `--network none`, twice -> byte-identical. |
| 12 | Business & roadmap | Monetization, virality, and the Redrob super-app fit. |
| 13 | Team & contact | Who built it and how to reach us. |

## Narrative arc
1. **Hook (1-3):** the problem is real and the dataset is adversarial — it punishes naive keyword counting on purpose.
2. **Solution (4-7):** a three-plane hybrid funnel that judges evidence, not titles, and structurally guarantees no trap survives.
3. **Proof (8-11):** measured speed, validity, determinism, an offline reproduction, and a cinematic product on top.
4. **Future (12-13):** how this becomes a business inside Redrob, and who is behind it.
