#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
io_threads=${1:?Specify measured I/O concurrency per worker (1-32)}
max_batches=${2:-0}
force_overflow=${3:-0}
overflow_mount=$(findmnt -rn -S UUID=62C9-C390 -o TARGET)
[[ -n "$overflow_mount" ]]
workers=$(autosize_workers 2048 6144)
if (( workers > 4 )); then workers=4; fi
autosize_report 'V7 parallel option capture' "$workers"
systemd-run --user --collect --unit=healys-v7-capture-v4-20260927 \
  --description='V7 concurrent option capture, preserving original packs' \
  --property="WorkingDirectory=$PWD" --property=MemoryHigh=14G \
  --property=MemoryMax=14G --property=MemorySwapMax=0 --property="CPUQuota=$((workers*200))%" --property=CPUWeight=50 \
  --property=TasksMax=256 --property=Nice=10 --property=Restart=no \
  --property=TimeoutStopSec=600 --property=KillMode=mixed \
  "$PWD/venv/bin/python" -u "$PWD/scripts/run_v7_capture_campaign_v4.py" \
  --audit nn_meta/validation/v7-3-entry-union-20260926 \
  --existing-index nn_meta/validation/v7-execution-sample-index-20260927-r12 \
  --output nn_meta/data_v7/entry-campaign-20260927 \
  --state nn_meta/validation/v7-entry-campaign-v4-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v2-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v3-20260927 \
  --workers "$workers" --io-threads "$io_threads" --max-batches "$max_batches" \
  --overflow-mount "$overflow_mount" --force-overflow-batches "$force_overflow"
