#!/usr/bin/env bash
# Wall-clock + peak RSS for rank.py using /usr/bin/time -v (falls back to check_budget.py).
set -euo pipefail
export OMP_NUM_THREADS=1 PYTHONHASHSEED=0
CANDIDATES="${1:-./candidates.jsonl}"
OUT="${2:-./submission.csv}"
ARTIFACTS="${3:-./artifacts}"

if command -v /usr/bin/time >/dev/null 2>&1; then
  /usr/bin/time -v python rank.py --candidates "$CANDIDATES" --out "$OUT" --artifacts "$ARTIFACTS"
else
  python scripts/check_budget.py --candidates "$CANDIDATES" --out "$OUT" --artifacts "$ARTIFACTS"
fi
