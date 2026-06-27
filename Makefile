# IndiaRuns / ATLAS — Makefile
# Plane B (graded) targets are the load-bearing ones; Plane A targets regenerate artifacts.

PY ?= python3
CANDIDATES ?= ./candidates.jsonl
SAMPLE ?= ./data/sample_candidates.jsonl
OUT ?= ./submission.csv

.PHONY: help install install-precompute test lint rank rank-sample validate sample \
        precompute-sample reproduce prove clean

help:
	@echo "Targets:"
	@echo "  install            install rank-time deps (numpy, sklearn)"
	@echo "  install-precompute install Plane A deps (sentence-transformers, xgboost, ...)"
	@echo "  test               run pytest"
	@echo "  lint               run ruff"
	@echo "  precompute-sample  build sample artifacts (fallback/local mode) from the 100-line sample"
	@echo "  rank-sample        run rank.py on the sample -> submission.csv"
	@echo "  rank               run rank.py on \$$(CANDIDATES) -> \$$(OUT)"
	@echo "  validate           validate \$$(OUT) with the vendored validator"
	@echo "  prove              precompute-sample + rank-sample + validate + test"

install:
	$(PY) -m pip install -r requirements-rank.txt

install-precompute:
	$(PY) -m pip install -r requirements-precompute.txt

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

sample:
	$(PY) data/make_sample.py

precompute-sample:
	$(PY) precompute/run_all.py --candidates $(SAMPLE) --artifacts ./artifacts_sample --mode local

rank-sample:
	$(PY) rank.py --candidates $(SAMPLE) --out ./submission_sample.csv --artifacts ./artifacts_sample

rank:
	$(PY) rank.py --candidates $(CANDIDATES) --out $(OUT)

validate:
	$(PY) validate_submission.py $(OUT)

reproduce:
	bash reproduce.sh

prove: precompute-sample rank-sample
	$(PY) validate_submission.py ./submission_sample.csv
	$(PY) -m pytest

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache .ruff_cache
	rm -f submission_sample.csv
