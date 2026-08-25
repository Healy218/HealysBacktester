#!/usr/bin/env bash
# scripts/backup_caches.sh — one-way sync of irreplaceable data caches to GCS.
#
# The home box holds the ONLY copy of every bar behind Massive's rolling
# 2-year entitlement (flat-file day-frames, per-contract bars, the 2017→ 1m
# underlying crawl, the PIT universe daily rows). None of that is in git or
# re-downloadable. This pushes it to the project bucket on a timer
# (deploy/systemd/healys-cache-backup.timer).
#
# Additive-only ON PURPOSE (no rsync -d): a local deletion — accidental or a
# bad script — must never propagate to the last remaining copy. Stale extra
# objects in the backup are the cheap failure mode.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

GSUTIL="${GSUTIL:-$HOME/google-cloud-sdk/bin/gsutil}"
DEST="gs://healys-backtester/backup/homebox"

for d in v3/data nn_meta/data_cache_v3 nn_meta/data_cache_v5 \
         nn_meta/data_cache_spx0; do
    echo "=== $(date -Is) rsync $d"
    "$GSUTIL" -m -q rsync -r -x '.*\.tmp$' "$d" "$DEST/$d"
done
echo "=== $(date -Is) backup complete"
