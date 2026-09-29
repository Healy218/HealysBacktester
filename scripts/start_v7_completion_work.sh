#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
case "${1:?Specify plan or references}" in
  plan)
    systemd-run --user --collect --unit=healys-v7-execution-plan-20260928 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=1500M \
      --property=MemoryMax=2G --property=MemorySwapMax=0 --property=CPUQuota=100% \
      --property=Nice=10 --property=Restart=no --property=TasksMax=64 \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/plan_v7_full_execution.py \
      --audit nn_meta/validation/v7-3-entry-union-20260926 \
      --output nn_meta/validation/v7-full-execution-plan-20260928
    ;;
  references)
    threads=$(autosize_workers 64 16384)
    (( threads <= 16 )) || threads=16
    autosize_report 'V7 reference recovery' "$threads"
    systemd-run --user --collect --unit=healys-v7-reference-recovery-20260928 \
      --property="WorkingDirectory=$PWD" --property=MemoryHigh=1G \
      --property=MemoryMax=2G --property=MemorySwapMax=0 --property=CPUQuota=100% \
      --property=Nice=10 --property=Restart=no --property=TasksMax=64 \
      --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
      "$PWD/venv/bin/python" -u scripts/recover_v7_reference_lists.py \
      --audit nn_meta/validation/v7-reference-reconciliation-20260928-full-r0 \
      --output nn_meta/data_v7/reference-list-recovery-20260928 \
      --state nn_meta/validation/v7-reference-list-recovery-20260928 --threads "$threads"
    ;;
  *) exit 2;;
esac
