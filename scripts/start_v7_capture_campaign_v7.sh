#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
worker_cap=${1:?Specify measured worker ceiling (4, 6, 8, or 12)}
io_threads=${2:-32}
max_batches=${3:-0}
force_overflow=${4:-0}
[[ "$worker_cap" =~ ^(4|6|8|12)$ && "$io_threads" =~ ^[0-9]+$ && "$max_batches" =~ ^[0-9]+$ && "$force_overflow" =~ ^[0-9]+$ ]]
(( io_threads >= 1 && io_threads <= 32 ))
overflow_mount=$(findmnt -rn -S UUID=62C9-C390 -o TARGET)
[[ -n "$overflow_mount" ]]
# 1 GiB per worker, at most 12 GiB plus 2 GiB headroom; shared memory guard remains active.
workers=$(autosize_workers 1024 6144)
if (( workers > worker_cap )); then workers=$worker_cap; fi
autosize_report 'V7 parallel option capture' "$workers"
systemd-run --user --collect --unit=healys-v7-capture-v7-20260927 \
  --description='V7 concurrent option capture, preserving original packs' \
  --property="WorkingDirectory=$PWD" --property=MemoryHigh=14G \
  --property=MemoryMax=14G --property=MemorySwapMax=0 --property=CPUQuota=800% --property=CPUWeight=50 \
  --property="TasksMax=$((workers*(io_threads+4)+32))" --property=Nice=10 --property=Restart=no \
  --property=TimeoutStopSec=600 --property=KillMode=mixed \
  "$PWD/venv/bin/python" -u "$PWD/scripts/run_v7_capture_campaign_v7.py" \
  --audit nn_meta/validation/v7-3-entry-union-20260926 \
  --existing-index nn_meta/validation/v7-execution-sample-index-20260927-r12 \
  --output nn_meta/data_v7/entry-campaign-20260927 \
  --state nn_meta/validation/v7-entry-campaign-v7-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v2-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v3-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v4-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v5-20260927 \
  --parent-state nn_meta/validation/v7-entry-campaign-v6-20260927 \
  --workers "$workers" --io-threads "$io_threads" --max-batches "$max_batches" \
  --overflow-mount "$overflow_mount" --force-overflow-batches "$force_overflow"
