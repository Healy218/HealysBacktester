#!/usr/bin/env bash
# Prebuild flat-file 15m day-frames for the 120-symbol big-run universe over
# the ~2y read-entitlement window. Long-running; launch detached.
set -euo pipefail
cd /home/mrhea/HealysBacktester

U=$(./venv/bin/python -c "import json;print(','.join(json.load(open('v3/artifacts/universe_120.json'))))")
echo "universe: $(echo "$U" | tr ',' '\n' | wc -l) symbols"

exec ./venv/bin/python -m v3.flatfiles \
  --start 2024-08-01 --end 2026-07-11 \
  --cache nn_meta/data_cache_v3 --universe "$U"
