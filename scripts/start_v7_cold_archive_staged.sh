#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
unset OMP_NUM_THREADS OMP_THREAD_LIMIT
workers=$(autosize_workers 1536 6144)
autosize_report 'V7 zstd-22 SSD staging and serial MRHA publication' "$workers"
exec ./venv/bin/python scripts/archive_v7_cold_staged.py --workers "$workers" --reclaim
