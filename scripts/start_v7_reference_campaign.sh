#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
cap=${1:-32}
max_batches=${2:-0}
[[ "$cap" =~ ^[0-9]+$ && "$max_batches" =~ ^[0-9]+$ ]]
(( cap >= 1 && cap <= 64 ))
# I/O threads use bounded 64-KiB responses; leave paper scanner/desktop headroom.
unset OMP_NUM_THREADS
workers=$(autosize_workers 64 12288)
(( workers <= cap )) || workers=$cap
autosize_report 'V7 dated references' "$workers"
systemd-run --user --collect --unit=healys-v7-references-20260928 \
  --description='V7 exact dated reference acquisition' --property="WorkingDirectory=$PWD" \
  --property=MemoryHigh=1G --property=MemoryMax=2G --property=MemorySwapMax=0 \
  --property=CPUQuota=100% --property=CPUWeight=25 --property=Nice=10 \
  --property=TimeoutStopSec=180 --property=KillMode=mixed \
  --setenv=OMP_NUM_THREADS=1 --setenv=OPENBLAS_NUM_THREADS=1 \
  "$PWD/venv/bin/python" -u "$PWD/scripts/run_v7_reference_campaign.py" \
  --plan nn_meta/validation/v7-dated-reference-demand-20260927 \
  --output nn_meta/data_v7/dated-reference-campaign-20260928 \
  --state nn_meta/validation/v7-reference-campaign-20260928 \
  --reuse-root nn_meta/data_v7/contract-reference-20260915 \
  --reuse-root nn_meta/data_v7/entry-joined-sample-references-20260926 \
  --workers "$workers" --max-batches "$max_batches"
