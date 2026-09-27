#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
# Retain memory for the V7 downloader and desktop. 16 is the frozen scanner's
# accepted API ceiling; the selected count is derived from current resources.
workers=$(autosize_workers 384 10240)
budget_workers=$(( (8192 - 2048) / 384 ))
(( workers > budget_workers )) && workers=$budget_workers
(( workers > 16 )) && workers=16
autosize_report 'V6 Alpaca scanner' "$workers"
exec ./venv/bin/python -m scripts.run_v6_alpaca_runtime scan --workers "$workers" "$@"
