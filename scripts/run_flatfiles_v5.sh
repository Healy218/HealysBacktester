#!/usr/bin/env bash
# Prebuild flat-file 15m option day-frames for the v5 PIT universe.
#
# Differences from the v31 launcher (run_flatfiles_parallel.sh):
#   - Universe = the union of the frozen PIT monthlies (453 names) PLUS the
#     reverse-aliased historical roots (XYZ traded as SQ, FISV as FI, DRAM as
#     BITF) — the raw files carry the root that was live on that day.
#   - Cache = nn_meta/data_cache_v5. The v31 frames in data_cache_v3 are
#     120-name-FILTERED and build_day_frame skips existing files, so reusing
#     that dir would silently keep the narrow frames. v31's inputs stay frozen.
#   - Worker count from autosize (a v3.flatfiles worker peaks ~1.1GB on the
#     whole-market minute parse).
#
# Idempotent per day; rerun to resume. Entitlement rolls daily — the window
# start below is the measured wall (2026-08-24); recrawls can't go earlier.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
. scripts/lib/autosize.sh

pkill -f 'v3.flatfiles' 2>/dev/null || true
sleep 2
# newest two frames may be partial writes from a killed run (`|| true`:
# nothing to clean on the first run, when the dir does not exist yet)
{ ls -t nn_meta/data_cache_v5/flatfiles_15m/*.parquet 2>/dev/null || true; } \
  | head -2 | xargs -r rm -f

U=$(./venv/bin/python - <<'EOF'
import json, sys
sys.path.insert(0, '.')
from nn_meta.config import TICKER_ALIASES
from nn_meta.universe_pit import ARTIFACT_DIR
members = {m["ticker"] for f in sorted(ARTIFACT_DIR.glob("*.json"))
           for m in json.loads(f.read_text())["members"]}
if not members:
    sys.exit("no frozen PIT months — freeze the universe first")
old_roots = {old for old, new in TICKER_ALIASES.items() if new in members}
print(",".join(sorted(members | old_roots)))
EOF
)
echo "universe: $(echo "$U" | tr ',' '\n' | wc -l) roots (PIT union + reverse aliases)"

START=2024-08-26
END=$(date -d 'yesterday' +%F)
N=$(autosize_workers 1100)
autosize_report "flatfiles_v5" "$N"

# split [START, END] into N contiguous shards, one worker each
mapfile -t BOUNDS < <(./venv/bin/python - "$START" "$END" "$N" <<'EOF'
import sys
from datetime import date, timedelta
s, e, n = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]), int(sys.argv[3])
days = (e - s).days
for i in range(n):
    a = s + timedelta(days=days * i // n + (i > 0))
    b = s + timedelta(days=days * (i + 1) // n)
    print(a, b)
EOF
)

i=0
for span in "${BOUNDS[@]}"; do
  i=$((i + 1))
  read -r a b <<< "$span"
  setsid nohup ./venv/bin/python -m v3.flatfiles \
    --start "$a" --end "$b" --cache nn_meta/data_cache_v5 --universe "$U" \
    > "logs/flatfiles_v5_w$i.log" 2>&1 < /dev/null &
  echo "  worker $i: $a → $b  (pid $!)"
done

sleep 4
echo "running workers: $(pgrep -fc 'v3.flatfiles' || true)"
echo "frames so far:   $(ls nn_meta/data_cache_v5/flatfiles_15m/ 2>/dev/null | wc -l)"
