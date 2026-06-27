#!/usr/bin/env bash
# Reproduce the graded submission from frozen artifacts. CPU-only, no network.
set -euo pipefail

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONHASHSEED=0

CANDIDATES="${1:-./candidates.jsonl}"
OUT="${2:-./submission.csv}"
ARTIFACTS="${3:-./artifacts}"

python rank.py --candidates "$CANDIDATES" --out "$OUT" --artifacts "$ARTIFACTS"
python validate_submission.py "$OUT"
echo "Reproduced: $OUT"
