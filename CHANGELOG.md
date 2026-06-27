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
