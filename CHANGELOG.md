# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- **Plane A upgraded to real NVIDIA NIM endpoints.** Embeddings are now
  `nvidia/nv-embedqa-e5-v5` (1024-d) over all 100K narratives + JD clauses, and the
  shortlist re-rank & reasoning are real `meta/llama-3.3-70b-instruct` judgments over the
  **full 1,226-row shortlist** (1,226 real judgments), frozen into checksummed artifacts.
  The local BGE / TF-IDF embeddings and the `claude -p` LLM-judge path remain shipped as
  the no-key degradation chain. The graded `rank.py` reads only the frozen artifacts and
  still needs no key or network (reproduces after key rotation).
- Refreshed frozen artifacts, sample artifacts, web artifacts, `submission.csv`, and all
  docs/metadata to the NVIDIA-derived numbers.

### Added
- Monorepo scaffold: packaging, requirements (rank / precompute / dev), license, Makefile.
- Plane B graded ranker (`rank.py`) — CPU-only, no-network, frozen-artifact pipeline.
- Plane A pre-compute scripts (`precompute/`) — embeddings, lexical fit, labels,
  shortlist + recall gate, LLM re-rank (degradable), monotone LTR, reasoning.
- Clean structural honeypot defense (clean-201 exclude set; salary inversion never flagged).
- Shared `features.py` extractor (no train/serve skew) with monotone signs in `feature_meta.json`.
- Compliance test suite: validator, determinism, no-network, sentinels, gate, budget.
- ATLAS web app (Plane C) over frozen artifacts; `/sandbox` runs the real `rank.py` offline.
- Infra: Dockerfiles (ranker/sandbox/api/web), HF Space, GCP IaC, Cloud Build, CI workflows.
- Documentation set: top-level `README.md` blueprint with the three-plane mermaid map;
  `docs/blueprint.md`, `docs/architecture.md` (5 mermaid diagrams), `docs/honeypot_defense.md`,
  `docs/anti_trap_reasoning.md`, `docs/reproducibility.md`, `docs/results.md` (expanded with
  the headline table + top-20 listing), `docs/data_card.md`, `docs/interview_prep.md`.
- `submission_metadata.yaml` filled from the template with real verified values
  (`uses_gpu_for_inference: false`, `has_network_during_ranking: false`,
  `pre_computation_required: true`, honest `ai_usage_summary`, <=200-word methodology).

### Verified (real full 100K pool)
- `rank.py`: 87.9 s wall-clock, 2.25 GB peak RSS, CPU-only, no network; caps 300 s / 16 GB.
- Determinism: byte-identical, `sha256 f39f5fa551b26cbab98d79c3cd1d72c0a6a4dacde49df6e1337f1083e421c60c`.
- Validator: "Submission is valid." 0 honeypots in top-100 and top-10.
- Shortlist recall gate PASS (proxy-Tier-5 100%, Tier-4 100% inside K=1200); fusion ships BLEND.
- `docker run --network none --cpus=4 --memory=16g` produced a valid CSV offline.
