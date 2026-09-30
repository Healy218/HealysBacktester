#!/usr/bin/env bash
# Resume the selected, source-bound campaign without recapturing completed data.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
workers=$(autosize_workers 3072 12288)
(( workers <= 1 )) || workers=1
autosize_report 'V7 overnight pending replay' "$workers"
exec ./venv/bin/python - "$workers" <<'PY'
import json,os,sys
from pathlib import Path
root=Path.cwd()
selected=json.loads((root/'nn_meta/validation/v7-evening-continuation-20260929-r0/selected-replay.json').read_text())
state=Path(selected['campaign'])
preflight=json.loads((root/'nn_meta/validation/v7-overnight-resume-20260929-r0/preflight.json').read_text())
if str(state)!=preflight['campaign']:
    raise ValueError('Selected campaign differs from verified checkpoint')
declaration=json.loads((state/'declaration.json').read_text())
command=[sys.executable,'-u',str(root/'scripts/run_v7_pending_campaign.py')]
for key,value in declaration['arguments'].items():
    command.extend(['--'+key,value])
command.extend(['--state',str(state),'--workers',sys.argv[1],'--slice-seconds','300','--max-seconds','14400'])
os.execv(sys.executable,command)
PY
