#!/usr/bin/env bash
# Home-box v5 build worker (user decision 2026-09-01): walk the spec's
# symbols in REVERSE alphabetical order and build any symbol the bucket
# doesn't have yet — meeting the cloud fleet (which walks forward) in the
# middle. The bucket IS the coordination: both sides skip-check
# out/v5/meta_rows/<sym>.parquet before starting and publish there when
# done, so a near-middle collision costs at most one duplicated symbol.
#
# Caveat (accepted): rows built here come from the venv, not the docker
# image — BLAS-level float differences vs cloud-built rows are possible.
# v5 has no identity-diff gate (that was the v31 rebuild), so heterogeneous
# provenance is fine; the handoff records which stage ran where.
#
# Run DETACHED (harness background tasks get killed on this box):
#   setsid nohup scripts/run_build_v5_local.sh > logs/build_v5_local.log 2>&1 &
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
. scripts/lib/autosize.sh
export NN_META_POOL=v5
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
BUCKET=gs://healys-backtester
OUTB="$BUCKET/out/v5"
ART=nn_meta/artifacts_v5
PART="$ART/meta_partial_local"
mkdir -p "$PART" "$ART/meta_rows" "$ART/meta_marks" logs

# ~6.4GB peak RSS per build worker (DKNG measurement, 2026-08-25)
WORKERS=${WORKERS:-$(autosize_workers 6600 3072)}
echo "workers: $WORKERS"

gsutil -q cp "$BUCKET/artifacts_v5_in/baseline_spec.json" "$ART/baseline_spec.json"

# push family partials every 4 min — a reboot/kill loses at most one family
( while sleep 240; do
    gsutil -m -q rsync -r "$PART" "$OUTB/meta_partial" 2>/dev/null || true
  done ) &
PART_SYNC=$!
trap 'kill $PART_SYNC 2>/dev/null || true' EXIT

build_one() {
  sym=$1
  if gsutil -q stat "$OUTB/meta_rows/${sym}.parquet" 2>/dev/null; then
    echo "[$sym] already in bucket — skip"; return 0
  fi
  gsutil -m -q cp "$OUTB/meta_partial/${sym}.*" "$PART/" 2>/dev/null || true
  ./venv/bin/python -m nn_meta.build_meta_dataset --symbols "$sym" --marks \
      --partial-dir "$PART" || { echo "[$sym] BUILD FAILED"; return 1; }
  # marks before rows, same commit order as the cloud task
  [ -f "$ART/meta_marks/${sym}.parquet" ] && \
    gsutil -q cp "$ART/meta_marks/${sym}.parquet" "$OUTB/meta_marks/"
  gsutil -q cp "$ART/meta_rows/${sym}.parquet" "$OUTB/meta_rows/"
  echo "[$sym] published $(date -u +%H:%M:%SZ)"
}
export -f build_one
export OUTB ART PART

./venv/bin/python - <<'PY' | xargs -P "$WORKERS" -I{} bash -c 'build_one "$1"' _ {}
import json
s = json.load(open("nn_meta/artifacts_v5/baseline_spec.json"))
for sym in sorted(s["symbols"], reverse=True):
    print(sym)
PY
echo "LOCAL-BUILD-DONE $(date -u +%FT%TZ)"
