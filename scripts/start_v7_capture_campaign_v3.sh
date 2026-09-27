#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
io_threads=${1:?Specify measured I/O concurrency per worker (1-16)}
max_batches=${2:-0}
workers=$(autosize_workers 2048 6144)
if (( workers > 4 )); then workers=4; fi
autosize_report 'V7 parallel option capture' "$workers"
systemd-run --user --collect --unit=healys-v7-capture-v3-20260927 \
  --description='V7 concurrent option capture, preserving original packs' \
  --property="WorkingDirectory=$PWD" --property=MemoryHigh=10G \
  --property=MemoryMax=14G --property=MemorySwapMax=0 --property=CPUQuota=400% \
  --property=TasksMax=256 --property=Nice=10 --property=Restart=no \
  --property=TimeoutStopSec=600 --property=KillMode=mixed \
  "$PWD/venv/bin/python" -u "$PWD/scripts/run_v7_capture_campaign_v3.py" \
  --audit nn_meta/validation/v7-3-entry-union-20260926 \
  --existing-index nn_meta/validation/v7-execution-sample-index-20260927-r12 \
  --output nn_meta/data_v7/entry-campaign-20260927 \
  --state nn_meta/validation/v7-entry-campaign-v3-20260927 \
  --legacy-state nn_meta/validation/v7-entry-campaign-20260927 \
  --parallel-parent nn_meta/validation/v7-entry-campaign-v2-20260927 \
  --workers "$workers" --io-threads "$io_threads" --max-batches "$max_batches" \
  --max-new-bytes 100000000000
