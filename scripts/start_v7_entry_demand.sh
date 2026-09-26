#!/usr/bin/env bash
# Start the full, frozen V7 entry-demand scheduler as a resource-bounded user service.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
REPO_ROOT=$PWD
source scripts/lib/autosize.sh

unit=''
completion=''
output=''
storage_plan=''
workers=''
while (($#)); do
  case "$1" in
    --unit) unit=$2; shift 2 ;;
    --completion) completion=$2; shift 2 ;;
    --output) output=$2; shift 2 ;;
    --storage-plan) storage_plan=$2; shift 2 ;;
    --workers) workers=$2; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$unit" || -z "$completion" || -z "$output" || -z "$storage_plan" ]]; then
  echo 'Require --unit --completion --output --storage-plan [--workers 1..4]' >&2
  exit 2
fi
if [[ -z "$workers" ]]; then
  workers=$(autosize_workers 3500 8192)
  ((workers > 4)) && workers=4
fi
[[ "$workers" =~ ^[1-4]$ ]] || { echo 'Workers must be 1..4' >&2; exit 2; }
[[ "$unit" =~ ^healys-v7-entry-demand-[a-zA-Z0-9-]+$ ]] || { echo 'Use a dated V7 demand service name' >&2; exit 2; }
budget=$(./venv/bin/python - "$storage_plan" <<'PY'
import json, sys
from pathlib import Path
from nn_meta.v7.storage import verify, sha
p=Path(sys.argv[1]);verify(p)
d=json.loads((p/'report.json').read_text())
if d.get('schema')!='v7-demand-storage-plan-v1' or d.get('securities')!=591:
    raise ValueError('Full-scope demand storage plan required')
if any(sha(path)!=digest for path,digest in d['inputs'].items()):
    raise ValueError('Storage planning inputs changed')
b=d['stage_output_limit_bytes']
if (type(b) is not int or b<=0 or d['stress_forecast_bytes']>b or
        d['baseline_project_allocated_bytes']+b>d['total_project_budget_bytes'] or
        d['required_free_reserve_bytes']<100*1024**3):
    raise ValueError('Storage allocation does not cover the forecast/project budget')
print(b)
PY
)
# The unchanged scheduler checks the completion proof, output lineage and live
# free space in planning mode before any service is submitted.
./venv/bin/python scripts/run_v7_entry_demand.py --completion "$completion" \
  --output "$output" --workers "$workers" --max-output-bytes "$budget"
autosize_report 'V7 entry demand' "$workers"
mkdir -p "$output"
output=$(realpath "$output")
completion=$(realpath "$completion")
systemd-run --user --unit="$unit" \
  --description='V7 full 591-security entry feature demand (no provider capture)' \
  --property="WorkingDirectory=$REPO_ROOT" \
  --property="CPUQuota=$((workers * 100))%" \
  --property="MemoryHigh=$((workers * 3 + 2))G" \
  --property="MemoryMax=$((workers * 3 + 4))G" \
  --property=MemorySwapMax=0 --property=Nice=10 --property=IOWeight=25 \
  --property=KillMode=control-group --property=Restart=no \
  --property=NoNewPrivileges=yes --property=RestrictAddressFamilies=AF_UNIX \
  --property="StandardOutput=append:$output/controller.log" \
  --property="StandardError=append:$output/controller.log" \
  --setenv=PYTHONDONTWRITEBYTECODE=1 \
  "$REPO_ROOT/venv/bin/python" "$REPO_ROOT/scripts/run_v7_entry_demand.py" \
  --completion "$completion" --output "$output" \
  --workers "$workers" --max-output-bytes "$budget" --run
