#!/usr/bin/env bash
# Parallel flat-file day-frame download: 4 workers on disjoint date ranges.
# Day-frames are idempotent (build_day_frame skips existing), so ranges may
# overlap already-done days harmlessly and never collide with each other.
# The live scanner is on the CLOUD SERVER, not this box, so the only other
# local load is the hourly StockTwits job — 4 workers (~4.4GB of 7.6) is safe.
set -euo pipefail
cd /home/mrhea/HealysBacktester

# stop any single run + clean the two newest frames (possible partial writes)
pkill -f 'v3.flatfiles' 2>/dev/null || true
sleep 2
ls -t nn_meta/data_cache_v3/flatfiles_15m/*.parquet 2>/dev/null | head -2 | xargs -r rm -f

U=$(./venv/bin/python -c "import json;print(','.join(json.load(open('v3/artifacts/universe_120.json'))))")

launch(){  # $1=start $2=end $3=tag
  setsid nohup ./venv/bin/python -m v3.flatfiles \
    --start "$1" --end "$2" --cache nn_meta/data_cache_v3 --universe "$U" \
    > "v3_flatfiles_$3.log" 2>&1 < /dev/null &
  echo "  worker $3: $1 → $2  (pid $!)"
}

launch 2025-02-01 2025-05-15 w1
launch 2025-05-16 2025-09-15 w2
launch 2025-09-16 2026-01-15 w3
launch 2026-01-16 2026-07-11 w4

sleep 4
echo "running workers: $(pgrep -fc 'v3.flatfiles')"
echo "frames so far:   $(ls nn_meta/data_cache_v3/flatfiles_15m/ | wc -l)"
