#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
unset OMP_NUM_THREADS OMP_THREAD_LIMIT
threads=$(autosize_workers 4096 8192)
autosize_report 'V7 cold archive zstd-22' "$threads"
exec ./venv/bin/python scripts/archive_v7_cold.py run --threads "$threads" --reclaim
