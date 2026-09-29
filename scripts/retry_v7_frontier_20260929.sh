#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
state=nn_meta/validation/v7-frontier-capture-20260929-r0
remaining(){
  ./venv/bin/python -c 'from datetime import datetime; from zoneinfo import ZoneInfo; now=datetime.now(ZoneInfo("America/Chicago")); print(int((now.replace(hour=15, minute=0, second=0, microsecond=0)-now).total_seconds()))'
}
# This wrapper holds no data workers until the initial service is fully stopped.
while systemctl --user --quiet is-active healys-v7-frontier-capture-20260929.service; do
  (( $(remaining) > 60 )) || { echo 'Retry deferred at daytime cutoff.'; exit 0; }
  sleep 15
done
stamp=$(date -u +%Y%m%dT%H%M%SZ)
for attempt in 1 2 3; do
  budget=$(remaining)
  (( budget > 60 )) || { echo 'Retry deferred at daytime cutoff.'; exit 0; }
  # Archive terminal receipts before the unchanged resumable controller updates them.
  need=$(./venv/bin/python - "$state" "$stamp" "$attempt" <<'PY'
import json,sys
from pathlib import Path
from incubator.continual.storage import write
root=Path(sys.argv[1]);doc=json.loads((root/'progress.json').read_text())
if doc['status'] not in {'failed','checkpointed','captured_snapshot'}:
    raise SystemExit('Prior capture has no terminal receipt; do not race it')
target=root/'retry-history'/sys.argv[2]/sys.argv[3]
for name in ['progress.json','index-receipt.json']:
    if (root/name).exists():write(target/name,json.loads((root/name).read_text()))
print(int(doc['capture_windows_complete'] < doc['capture_windows_required']))
PY
)
  (( need )) || { echo 'Frozen quote snapshot fully captured.'; exit 0; }
  workers=$(autosize_workers 1024 20480)
  (( workers <= 4 )) || workers=4
  autosize_report 'V7 failed/missing frontier retry' "$workers"
  if ./venv/bin/python -u scripts/capture_v7_recovery_frontier.py capture \
      --plan nn_meta/validation/v7-recovery-frontier-20260929-r0 \
      --previous-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
      --output nn_meta/data_v7/execution-recovery-20260929-r0 \
      --state "$state" \
      --index-output "nn_meta/validation/v7-frontier-quote-index-20260929-retry-$stamp-$attempt" \
      --workers "$workers" --max-seconds "$budget"; then
    echo "Retry pass $attempt completed."
  else
    echo "Retry pass $attempt retained incomplete/provider-failed batches."
  fi
done
