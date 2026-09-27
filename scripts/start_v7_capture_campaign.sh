#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
workers=$(autosize_workers 2048 6144)
if (( workers > 4 )); then workers=4; fi
autosize_report 'V7 option capture' "$workers"
systemd-run --user --unit=healys-v7-capture-20260927 \
  --description='V7 frozen-demand option capture; model training has not started' \
  --property="WorkingDirectory=$PWD" --property=MemoryHigh=10G \
  --property=MemoryMax=14G --property=MemorySwapMax=0 --property=CPUQuota=400% \
  --property=TasksMax=128 --property=Nice=10 --property=Restart=no \
  "$PWD/venv/bin/python" -u "$PWD/scripts/run_v7_capture_campaign.py" \
  --audit nn_meta/validation/v7-3-entry-union-20260926 \
  --existing-index nn_meta/validation/v7-execution-sample-index-20260927-r12 \
  --output nn_meta/data_v7/entry-campaign-20260927 \
  --state nn_meta/validation/v7-entry-campaign-20260927 \
  --workers "$workers" --max-new-bytes 100000000000
