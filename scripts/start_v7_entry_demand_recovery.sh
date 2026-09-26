#!/usr/bin/env bash
# Resume demand only after sealed kernel equivalence and storage checks.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
REPO_ROOT=$PWD
source scripts/lib/autosize.sh
unit='' completion='' output='' storage_plan='' kernel_proof='' workers=''
while (($#)); do
  case "$1" in
    --unit) unit=$2; shift 2 ;;
    --completion) completion=$2; shift 2 ;;
    --output) output=$2; shift 2 ;;
    --storage-plan) storage_plan=$2; shift 2 ;;
    --kernel-proof) kernel_proof=$2; shift 2 ;;
    --workers) workers=$2; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$unit" || -z "$completion" || -z "$output" || -z "$storage_plan" || -z "$kernel_proof" ]]; then
  echo 'Require --unit --completion --output --storage-plan --kernel-proof [--workers 1..4]' >&2
  exit 2
fi
if [[ -z "$workers" ]]; then
  workers=$(autosize_workers 3500 8192)
  ((workers > 4)) && workers=4
fi
[[ "$workers" =~ ^[1-4]$ ]] || { echo 'Workers must be 1..4' >&2; exit 2; }
[[ "$unit" =~ ^healys-v7-entry-demand-[a-zA-Z0-9-]+$ ]] || { echo 'Use a dated V7 demand service name' >&2; exit 2; }
arguments=(--completion "$completion" --output "$output" --storage-plan "$storage_plan"
           --kernel-proof "$kernel_proof" --workers "$workers")
./venv/bin/python scripts/resume_v7_entry_demand.py "${arguments[@]}"
autosize_report 'V7 kernel recovery' "$workers"
mkdir -p "$output/kernel-recovery"
log=$(realpath "$output/kernel-recovery/controller.log" 2>/dev/null || realpath -m "$output/kernel-recovery/controller.log")
systemd-run --user --unit="$unit" \
  --description='V7 demand recovery with sealed kernel parity; no provider capture' \
  --property="WorkingDirectory=$REPO_ROOT" --property="CPUQuota=$((workers * 100))%" \
  --property="MemoryHigh=$((workers * 3 + 2))G" --property="MemoryMax=$((workers * 3 + 4))G" \
  --property=MemorySwapMax=0 --property=Nice=10 --property=IOWeight=25 \
  --property=KillMode=control-group --property=Restart=no \
  --property=NoNewPrivileges=yes --property=RestrictAddressFamilies=AF_UNIX \
  --property="StandardOutput=append:$log" --property="StandardError=append:$log" \
  --setenv=PYTHONDONTWRITEBYTECODE=1 \
  "$REPO_ROOT/venv/bin/python" "$REPO_ROOT/scripts/resume_v7_entry_demand.py" "${arguments[@]}" --run
