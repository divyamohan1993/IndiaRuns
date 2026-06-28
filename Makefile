# IndiaRuns / ATLAS — Makefile
# Plane B (graded) targets are the load-bearing ones; Plane A targets regenerate artifacts.

PY ?= python3
CANDIDATES ?= ./candidates.jsonl
SAMPLE ?= ./data/sample_candidates.jsonl
OUT ?= ./submission.csv

REGISTRY ?= indiaruns
TAG ?= latest

.PHONY: help install install-precompute test lint rank rank-sample validate sample \
        precompute-sample reproduce prove clean ranker sandbox web api deploy \
        docker-offline space

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
	@echo "  ranker             build the graded ranker docker image"
	@echo "  sandbox            build the judge sandbox docker image"
	@echo "  docker-offline     run the sandbox with --network none and validate the CSV"
	@echo "  space              build the Hugging Face Space (sandbox_link) image"
	@echo "  api                build the FastAPI api image"
	@echo "  web                build the Next.js/nginx web image"
	@echo "  reproduce          run reproduce.sh (CPU-only, no network)"
	@echo "  deploy             deploy to GCP Cloud Run via infra/bootstrap.sh (needs creds)"

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

# --- Docker images (all buildable with NO secrets) ---
ranker:
	docker build -f docker/Dockerfile.ranker -t $(REGISTRY)-ranker:$(TAG) .

sandbox:
	docker build -f docker/Dockerfile.sandbox -t $(REGISTRY)-sandbox:$(TAG) .

space:
	docker build -f spaces/Dockerfile -t $(REGISTRY)-space:$(TAG) .

api:
	docker build -f docker/Dockerfile.api -t $(REGISTRY)-api:$(TAG) .

web:
	docker build -f docker/Dockerfile.web -t $(REGISTRY)-web:$(TAG) .

# Run the sandbox image fully offline and validate the produced CSV.
docker-offline: ranker sandbox
	mkdir -p out
	docker run --rm --network none --cpus=4 --memory=16g -v "$(PWD)/out:/out" $(REGISTRY)-sandbox:$(TAG)
	docker run --rm --network none -v "$(PWD)/out:/out" --entrypoint python \
		$(REGISTRY)-ranker:$(TAG) validate_submission.py /out/submission.csv

# Deploy to GCP Cloud Run (operator supplies their own creds; no secret needed to build).
deploy:
	PROJECT_ID="$${PROJECT_ID:?set PROJECT_ID}" bash infra/bootstrap.sh

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache .ruff_cache out out2
	rm -f submission_sample.csv submission_ci*.csv submission_budget.csv
