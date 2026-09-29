#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
# Two isolated prefix workers fit the 12-GiB unit; leave RAM for V7 and desktop.
workers=$(autosize_workers 4500 12288)
[ "$workers" -le 2 ] || workers=2
autosize_report 'V6 continual r3' "$workers"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
exec ./venv/bin/python scripts/run_v6_continual_v3.py --config deploy/incubator-continual-v6-r3.json --workers "$workers" --threads "$workers" "$@"
