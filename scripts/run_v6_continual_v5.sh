#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
workers=$(autosize_workers 4500 8192)
[ "$workers" -le 4 ] || workers=4
autosize_report 'V6 append-only daily r5' "$workers"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
exec ./venv/bin/python scripts/run_v6_continual_v5.py --config deploy/incubator-continual-v6-r5.json --workers "$workers" --threads 2 "$@"
