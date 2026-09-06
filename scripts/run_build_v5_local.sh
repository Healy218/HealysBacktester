#!/usr/bin/env bash
# Home-box v5 build worker (user decision 2026-09-01): walk the spec's
# symbols in REVERSE alphabetical order and build any symbol the bucket
# doesn't have a validated checkpoint for, meeting the cloud fleet in the
# middle. Pull rows, marks and provenance; the builder verifies their input
# signature and coverage before skipping. Concurrent completion may duplicate
# work, so publication is per symbol with provenance committed last.
#
# Caveat (accepted): rows built here come from the venv, not the docker
# image — BLAS-level float differences vs cloud-built rows are possible.
# v5 has no identity-diff gate (that was the v31 rebuild), so heterogeneous
# provenance is fine; the handoff records which stage ran where.
#
# Run DETACHED (harness background tasks get killed on this box):
#   setsid nohup scripts/run_build_v5_local.sh > logs/build_v5_local.log 2>&1 &
set -euo pipefail
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
  # Pull the complete checkpoint including its feature-contract provenance.
  # The Python builder validates the manifest and mark coverage before skipping;
  # mere remote row existence is never a commit check.
  for item in "meta_rows/${sym}.parquet" "meta_rows/${sym}.provenance.json" "meta_marks/${sym}.parquet"; do
    gsutil -q cp "$OUTB/$item" "$ART/$item" 2>/dev/null || true
  done
  gsutil -m -q cp "$OUTB/meta_partial/${sym}.*" "$PART/" 2>/dev/null || true
  ./venv/bin/python -m nn_meta.build_meta_dataset --symbols "$sym" --marks \
      --partial-dir "$PART" || { echo "[$sym] BUILD FAILED"; return 1; }
  # Publish the row commit only after its marks are safely uploaded.
  gsutil -q cp "$ART/meta_marks/${sym}.parquet" "$OUTB/meta_marks/" || return 1
  gsutil -q cp "$ART/meta_rows/${sym}.parquet" "$OUTB/meta_rows/" || return 1
  gsutil -q cp "$ART/meta_rows/${sym}.provenance.json" "$OUTB/meta_rows/" || return 1
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
