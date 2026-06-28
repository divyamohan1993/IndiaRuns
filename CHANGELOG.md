# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
- `rank.py`: 73.5 s wall-clock, 2.01 GB peak RSS, CPU-only, no network; caps 300 s / 16 GB.
- Determinism: byte-identical, `sha256 694f86dd462772b7884e18e5b47a04e6b828f12abc91636c78c23b1b98cc457f`.
- Validator: "Submission is valid." 0 honeypots in top-100 and top-10.
- Shortlist recall gate PASS (proxy-Tier-5 100%, Tier-4 100% inside K=1200); fusion ships BLEND.
- `docker run --network none --cpus=4 --memory=16g` produced a valid CSV offline.
