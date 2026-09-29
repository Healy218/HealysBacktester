#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
case "${1:?Specify execution or compact}" in
  execution)
    workers=$(autosize_workers 2048 12288)
    (( workers <= 2 )) || workers=2
    autosize_report 'V7 execution discovery' "$workers"
    systemd-run --user --collect --unit=healys-v7-execution-campaign-20260928 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=5G \
      --property=MemoryMax=6G --property=MemorySwapMax=0 --property=CPUQuota=200% \
      --property=Nice=10 --property=Restart=no --property=TasksMax=128 \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/run_v7_execution_campaign.py \
      --plan nn_meta/validation/v7-full-execution-plan-20260928 \
      --base-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
      --entry-root nn_meta/data_v7/entry-campaign-20260927 \
      --references nn_meta/validation/v7-reference-reconciliation-20260928-full-r0 \
      --review nn_meta/validation/v7-reference-rename-review-20260928 \
      --hours nn_meta/validation/v7-dated-hours-20260927 \
      --blackouts nn_meta/validation/v7-contract-blackouts-20260927 \
      --state nn_meta/validation/v7-execution-campaign-20260928-r0 \
      --workers "$workers" --slice-seconds 600 --max-seconds 28800
    ;;
  compact)
    systemd-run --user --collect --unit=healys-v7-execution-scratch-20260928 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=96M \
      --property=MemoryMax=128M --property=MemorySwapMax=0 --property=CPUQuota=30% \
      --property=Nice=15 --property=Restart=no \
      "$PWD/venv/bin/python" -u scripts/compact_v7_execution_scratch.py \
      --root nn_meta/validation/v7-full-execution-plan-20260928 --watch-seconds 28800
    ;;
  *) exit 2;;
esac
