#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
unset OMP_NUM_THREADS OMP_THREAD_LIMIT
# Measured zstd-22 T3 working memory: 3.73 GiB anonymous/RSS. Budget
# 1.5 GiB/thread and retain 6 GiB host headroom; nproc remains the CPU cap.
workers=$(autosize_workers 1536 6144)
autosize_report 'V7 cold archive zstd-22 parallel shards' "$workers"
exec ./venv/bin/python scripts/archive_v7_cold_parallel.py --workers "$workers" --reclaim
