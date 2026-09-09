#!/usr/bin/env bash
# Weekly surface refresh for one pool, with a recorded outcome the heartbeat
# reads (2026-09-08 review, fixes 2 and 8): logs/refresh_status/<pool>.json
# holds start/finish stamps and the exit code, so a killed download no longer
# fails silently while the expert scans on a two-week-old IV surface.
#
#   scripts/run_refresh.sh v5               # download recent bars, then build the surface
#   scripts/run_refresh.sh v5 --build-only  # rebuild the surface from the cached bars
#
# Env: NN_META_DOWNLOAD_WORKERS (default 6 here; the 16-worker default was
# OOM-killed on the 8 GB host), REFRESH_RECENT_DAYS (default 10).
set -uo pipefail
POOL="${1:?usage: run_refresh.sh <pool> [--build-only]}"
BUILD_ONLY=0; [ "${2:-}" = "--build-only" ] && BUILD_ONLY=1
cd "$(dirname "$0")/.."
export NN_META_POOL="$POOL"
export NN_META_DOWNLOAD_WORKERS="${NN_META_DOWNLOAD_WORKERS:-6}"
DAYS="${REFRESH_RECENT_DAYS:-10}"
STATUS_DIR=logs/refresh_status
LOG="logs/surface_refresh_${POOL}.log"
mkdir -p "$STATUS_DIR"
started="$(date -u +%FT%TZ)"
write_status() {
    python3 - "$POOL" "$started" "$1" "$2" "$LOG" <<'PY' > "$STATUS_DIR/$POOL.json.tmp" && mv "$STATUS_DIR/$POOL.json.tmp" "$STATUS_DIR/$POOL.json"
import json, sys, datetime
pool, started, step, code, log = sys.argv[1:]
print(json.dumps({"pool": pool, "started": started, "step": step, "exit_code": int(code),
                  "finished": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  "log": log, "workers": __import__("os").environ.get("NN_META_DOWNLOAD_WORKERS")}))
PY
}
echo "=== refresh $POOL started $started (workers=$NN_META_DOWNLOAD_WORKERS, recent-days=$DAYS, build_only=$BUILD_ONLY) ==="
if [ "$BUILD_ONLY" -eq 1 ]; then
    write_status build_surface -1   # "running" marker: a still-running job reads as exit -1
else
    write_status download -1
    ./venv/bin/python -m nn_meta.download_universe --bars-and-surface-only --refresh-recent-days "$DAYS"
    code=$?
    if [ "$code" -ne 0 ]; then
        echo "=== refresh $POOL: download exited $code ==="
        write_status download "$code"; exit "$code"
    fi
    write_status build_surface -1
fi
./venv/bin/python -m nn_meta.build_surface
code=$?
echo "=== refresh $POOL: build_surface exited $code at $(date -u +%FT%TZ) ==="
write_status build_surface "$code"
exit "$code"
