#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
workers=$(autosize_workers 3000 8192)
# Measured pilot required before increasing this coexistence ceiling.
[ "$workers" -le 2 ] || workers=2
autosize_report 'V6 continual research' "$workers"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
exec ./venv/bin/python scripts/run_v6_continual.py --config deploy/incubator-continual-v6.json --workers "$workers" --threads "$workers" "$@"
