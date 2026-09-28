#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
# nproc honors OMP_NUM_THREADS; it must see CPU availability while sizing
# processes, then each numerical worker returns to one thread.
unset OMP_NUM_THREADS OMP_THREAD_LIMIT
workers=$(autosize_workers 1280 8192)
# Retain 2 GiB for the parent inside the installed 12 GiB service limit.
budget_workers=$(( (12288 - 2048) / 1280 ))
(( workers > budget_workers )) && workers=$budget_workers
(( workers > 16 )) && workers=16
autosize_report 'V6 Alpaca scanner v3' "$workers"
if [[ "${1:-}" == '--print-workers' ]]; then
  echo "$workers"
  exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
exec ./venv/bin/python -m scripts.run_v6_alpaca_runtime scan --workers "$workers" "$@"
