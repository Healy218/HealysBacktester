#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
# Bound this daytime recovery before the existing 15:45 Central V6 timer.
day_budget=$(./venv/bin/python -c 'from datetime import datetime; from zoneinfo import ZoneInfo; now=datetime.now(ZoneInfo("America/Chicago")); print(min(18000, int((now.replace(hour=15, minute=0, second=0, microsecond=0)-now).total_seconds())))')
(( day_budget >= 30 )) || { echo 'Daytime recovery window closed; preserve the V6 evening allocation.'; exit 1; }
case "${1:?Specify plan, snapshot, discovery, capture or references}" in
  plan)
    systemd-run --user --collect --unit=healys-v7-execution-plan-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=1500M \
      --property=MemoryMax=2G --property=MemorySwapMax=0 --property=CPUQuota=100% \
      --property=Nice=15 --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/plan_v7_full_execution.py \
      --audit nn_meta/validation/v7-3-entry-union-20260926 \
      --output nn_meta/validation/v7-full-execution-plan-20260928 --max-seconds "$day_budget"
    systemd-run --user --collect --unit=healys-v7-execution-scratch-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=96M \
      --property=MemoryMax=128M --property=MemorySwapMax=0 --property=CPUQuota=30% \
      --property=Nice=15 "$PWD/venv/bin/python" -u scripts/compact_v7_execution_scratch.py \
      --root nn_meta/validation/v7-full-execution-plan-20260928 --watch-seconds "$day_budget"
    ;;
  snapshot)
    exec ./venv/bin/python -u scripts/capture_v7_recovery_frontier.py snapshot \
      --parent nn_meta/validation/v7-execution-campaign-20260928-r1 \
      --previous-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
      --output nn_meta/validation/v7-recovery-frontier-20260929-r0
    ;;
  discovery)
    workers=$(autosize_workers 2048 16384)
    (( workers <= 2 )) || workers=2
    autosize_report 'V7 recovery discovery' "$workers"
    systemd-run --user --collect --unit=healys-v7-execution-recovery-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=5G \
      --property=MemoryMax=6G --property=MemorySwapMax=0 --property=CPUQuota=200% \
      --property=Nice=15 --property=TimeoutStopSec=90 --property=KillMode=mixed \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/run_v7_execution_recovery.py \
      --plan nn_meta/validation/v7-full-execution-plan-20260928 \
      --base-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
      --entry-root nn_meta/data_v7/entry-campaign-20260927 \
      --references nn_meta/validation/v7-reference-reconciliation-20260928-full-r0 \
      --review nn_meta/validation/v7-reference-rename-review-20260928 \
      --hours nn_meta/validation/v7-dated-hours-20260927 \
      --blackouts nn_meta/validation/v7-contract-blackouts-20260928-approved \
      --parent-state nn_meta/validation/v7-execution-campaign-20260928-r1 \
      --state nn_meta/validation/v7-execution-recovery-20260929-r0 \
      --workers "$workers" --slice-seconds 600 --max-seconds "$day_budget"
    ;;
  capture)
    workers=$(autosize_workers 1024 20480)
    (( workers <= 4 )) || workers=4
    autosize_report 'V7 actual-frontier capture' "$workers"
    systemd-run --user --collect --unit=healys-v7-frontier-capture-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=5G \
      --property=MemoryMax=6G --property=MemorySwapMax=0 --property=CPUQuota=200% \
      --property=Nice=15 --property=TimeoutStopSec=600 --property=KillMode=mixed \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/capture_v7_recovery_frontier.py capture \
      --plan nn_meta/validation/v7-recovery-frontier-20260929-r0 \
      --previous-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
      --output nn_meta/data_v7/execution-recovery-20260929-r0 \
      --state nn_meta/validation/v7-frontier-capture-20260929-r0 \
      --index-output nn_meta/validation/v7-frontier-quote-index-20260929-r5 \
      --workers "$workers" --max-seconds "$day_budget"
    ;;
  references)
    workers=$(autosize_workers 64 16384)
    (( workers <= 8 )) || workers=8
    autosize_report 'V7 actual held references' "$workers"
    systemd-run --user --collect --unit=healys-v7-held-references-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=768M \
      --property=MemoryMax=1G --property=MemorySwapMax=0 --property=CPUQuota=100% \
      --property=Nice=15 --property="RuntimeMaxSec=$day_budget" \
      --property=TimeoutStopSec=180 --property=KillMode=mixed \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/run_v7_reference_campaign.py \
      --plan nn_meta/validation/v7-held-reference-demand-20260929-r0 \
      --output nn_meta/data_v7/held-reference-campaign-20260929-r0 \
      --state nn_meta/validation/v7-held-reference-campaign-20260929-r0 \
      --workers "$workers"
    ;;
  retries)
    systemd-run --user --collect --unit=healys-v7-frontier-retry-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=5G \
      --property=MemoryMax=6G --property=MemorySwapMax=0 --property=CPUQuota=200% \
      --property=Nice=15 --property=TimeoutStopSec=600 --property=KillMode=mixed \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      /usr/bin/bash "$PWD/scripts/retry_v7_frontier_20260929.sh"
    ;;
  references-recover)
    workers=$(autosize_workers 64 16384)
    (( workers <= 4 )) || workers=4
    systemd-run --user --collect --unit=healys-v7-held-reference-recovery-20260929 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=768M \
      --property=MemoryMax=1G --property=MemorySwapMax=0 --property=CPUQuota=100% \
      --property=Nice=15 --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/recover_v7_reference_lists.py \
      --audit nn_meta/validation/v7-held-reference-reconciliation-20260929-r0 \
      --output nn_meta/data_v7/held-reference-recovery-20260929-r0 \
      --state nn_meta/validation/v7-held-reference-recovery-20260929-r0 --threads "$workers"
    ;;
  *) exit 2;;
esac
