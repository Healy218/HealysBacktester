#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
unset OMP_NUM_THREADS OMP_THREAD_LIMIT
workers=$(autosize_workers 1280 8192)
# Match the installed 16 GiB service limit, retaining 2 GiB for the parent.
budget_workers=$(( (16384 - 2048) / 1280 ))
(( workers > budget_workers )) && workers=$budget_workers
(( workers > 16 )) && workers=16
autosize_report 'V6 Alpaca scanner v10' "$workers"
if [[ "${1:-}" == '--print-workers' ]]; then
  echo "$workers"
  exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
# Frozen detection/model/price policy; held monitoring retries alongside detection.
exec ./venv/bin/python -m scripts.run_v6_alpaca_scanner_v10 --workers "$workers" "$@"
