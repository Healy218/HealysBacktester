#!/usr/bin/env bash
# Continue the finite pending replay queue until complete; no overall time cutoff.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
workers=$(autosize_workers 3072 12288)
(( workers <= 1 )) || workers=1
autosize_report 'V7 pending replay until complete' "$workers"
exec ./venv/bin/python scripts/finish_v7_pending_20260929.py --workers "$workers"
