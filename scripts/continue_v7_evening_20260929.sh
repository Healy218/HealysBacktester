#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
py="$PWD/venv/bin/python"
state=nn_meta/validation/v7-frontier-capture-20260929-r0
ops=nn_meta/validation/v7-evening-continuation-20260929-r0
stamp=$(date -u +%Y%m%dT%H%M%SZ)
# User selected evening continuation alongside V6; bounded operations, frozen producers.
end=$(( $(date +%s) + 18000 ))
remaining(){ echo $(( end - $(date +%s) )); }
phase(){
  "$py" - "$ops" "$1" "${2:-}" <<'PY'
import sys
from pathlib import Path
from datetime import datetime,timezone
from incubator.continual.storage import write
write(Path(sys.argv[1])/'progress.json',dict(phase=sys.argv[2],detail=sys.argv[3],updated_at=datetime.now(timezone.utc).isoformat(),full_execution_coverage=False))
PY
}
trap 'code=$?; if (( code )); then phase failed "exit $code"; fi' EXIT
phase waiting_for_capture
while systemctl --user --quiet is-active healys-v7-frontier-evening-20260929.service; do
  (( $(remaining) > 300 )) || { phase budget_exhausted; exit 0; }
  sleep 15
done
for attempt in 1 2; do
  need=$("$py" - "$state" "$ops" "$stamp" "$attempt" <<'PY'
import json,sys
from pathlib import Path
from incubator.continual.storage import write
root=Path(sys.argv[1]);d=json.loads((root/'progress.json').read_text())
if d['status'] not in ('captured_snapshot','checkpointed','failed'):raise SystemExit('No terminal capture receipt')
for name in ['progress.json','index-receipt.json']:
 if (root/name).exists():write(Path(sys.argv[2])/'history'/sys.argv[3]/sys.argv[4]/name,json.loads((root/name).read_text()))
print(int(d['capture_windows_complete']<d['capture_windows_required']))
PY
)
  (( need )) || break
  budget=$(remaining); (( budget > 900 )) || break
  (( budget <= 1800 )) || budget=1800
  workers=$(autosize_workers 1024 12288); (( workers <= 2 )) || workers=2
  phase quote_retry "$attempt"
  if "$py" -u scripts/capture_v7_recovery_frontier.py capture \
    --plan nn_meta/validation/v7-recovery-frontier-20260929-r0 \
    --previous-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
    --output nn_meta/data_v7/execution-recovery-20260929-r0 --state "$state" \
    --index-output "nn_meta/validation/v7-frontier-quote-index-20260929-evening-$stamp-retry$attempt" \
    --workers "$workers" --max-seconds "$budget"; then :; else
    echo "Retry $attempt retained explicit failures; checking its sealed receipt."
  fi
done
index=$("$py" - "$state" <<'PY'
import sys,json
from pathlib import Path
from nn_meta.v7.storage import sha,verify
r=json.loads((Path(sys.argv[1])/'index-receipt.json').read_text());p=Path(r['path'])
assert sha(p/'complete.json')==r['sha256'];verify(p)
print(p)
PY
)
blackouts=nn_meta/validation/v7-contract-blackouts-20260928-approved
if [[ -f nn_meta/validation/v7-contract-blackouts-20260929-held-approved/complete.json ]]; then
  blackouts=nn_meta/validation/v7-contract-blackouts-20260929-held-approved
fi
workers=$(autosize_workers 3072 12288); (( workers <= 1 )) || workers=1
campaign="nn_meta/validation/v7-pending-replay-campaign-20260929-$stamp"
"$py" - "$ops" "$index" "$blackouts" "$campaign" <<'PY'
import sys
from pathlib import Path
from incubator.continual.storage import write
from nn_meta.v7.storage import sha
write(Path(sys.argv[1])/'selected-replay.json',dict(quote_index=sys.argv[2],quote_index_sha256=sha(Path(sys.argv[2])/'complete.json'),blackouts=str(Path(sys.argv[3]).resolve()),blackouts_sha256=sha(Path(sys.argv[3])/'complete.json'),campaign=str(Path(sys.argv[4]).resolve())))
PY
budget=$(remaining); (( budget > 300 )) || { phase budget_exhausted; exit 0; }
(( budget <= 7200 )) || budget=7200
phase pending_replay "$campaign"
"$py" -u scripts/run_v7_pending_campaign.py \
  --plan nn_meta/validation/v7-full-execution-plan-20260928 \
  --replay-plan nn_meta/validation/v7-pending-replay-plan-20260929-r0 \
  --base-index "$index" --entry-root nn_meta/data_v7/entry-campaign-20260927 \
  --references nn_meta/validation/v7-reference-epoch-20260929-r0 \
  --review nn_meta/validation/v7-reference-rename-review-20260928 \
  --hours nn_meta/validation/v7-dated-hours-20260927 --blackouts "$blackouts" \
  --state "$campaign" --workers "$workers" --slice-seconds 300 --max-seconds "$budget"
# Continue previously unvisited discovery only after the new pending replay yields.
budget=$(remaining); (( budget > 300 )) || { phase checkpointed "$campaign"; exit 0; }
(( budget <= 1800 )) || budget=1800
workers=$(autosize_workers 2048 16384); (( workers <= 1 )) || workers=1
phase original_discovery
"$py" -u scripts/run_v7_execution_recovery.py \
  --plan nn_meta/validation/v7-full-execution-plan-20260928 \
  --base-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
  --entry-root nn_meta/data_v7/entry-campaign-20260927 \
  --references nn_meta/validation/v7-reference-reconciliation-20260928-full-r0 \
  --review nn_meta/validation/v7-reference-rename-review-20260928 \
  --hours nn_meta/validation/v7-dated-hours-20260927 \
  --blackouts nn_meta/validation/v7-contract-blackouts-20260928-approved \
  --parent-state nn_meta/validation/v7-execution-campaign-20260928-r1 \
  --state nn_meta/validation/v7-execution-recovery-20260929-r0 \
  --workers "$workers" --slice-seconds 300 --max-seconds "$budget"
phase checkpointed "$campaign"
