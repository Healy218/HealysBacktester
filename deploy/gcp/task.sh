#!/usr/bin/env bash
# One Batch task = one symbol shard of the dataset/marks build.
#
# Env (set by the job template / submit.sh):
#   BUCKET       gs://... bucket holding data_cache_v3/ and receiving outputs
#   TASK_MODE    "build" (default) — per-symbol rows+marks; "assemble" — final
#   SHARDS       total task count (BATCH_TASK_COUNT also works)
#   SYMBOLS      optional explicit comma list (pilot runs); overrides sharding
#
# Batch injects BATCH_TASK_INDEX. Everything is resume-safe: outputs are the
# same per-symbol checkpoints the local pipeline writes, synced to the bucket,
# so a preempted-and-retried task skips finished symbols.
set -euo pipefail
cd /app

echo "== task ${BATCH_TASK_INDEX:-?}/${SHARDS:-?} mode=${TASK_MODE:-build} =="

# Stage the raw option-bar cache + spec (read-only inputs).
mkdir -p nn_meta/data_cache_v3 nn_meta/artifacts_v31
gsutil -m -q rsync -r "${BUCKET}/data_cache_v3" nn_meta/data_cache_v3
gsutil -m -q rsync -r "${BUCKET}/artifacts_v31_in" nn_meta/artifacts_v31

# Resume: pull any checkpoints previous attempts already produced.
gsutil -m -q rsync -r "${BUCKET}/out/meta_rows"  nn_meta/artifacts_v31/meta_rows  || true
gsutil -m -q rsync -r "${BUCKET}/out/meta_marks" nn_meta/artifacts_v31/meta_marks || true

if [ "${TASK_MODE:-build}" = "assemble" ]; then
  ./venv/bin/python -m nn_meta.build_meta_dataset --assemble 2>/dev/null \
    || python -m nn_meta.build_meta_dataset --assemble
  gsutil -m -q cp nn_meta/artifacts_v31/meta_dataset.parquet \
                  nn_meta/artifacts_v31/*.marks.parquet "${BUCKET}/out/" || true
  exit 0
fi

if [ -n "${SYMBOLS:-}" ]; then
  MY_SYMS="$SYMBOLS"
else
  # Round-robin shard k of N over the frozen spec — same split rule as
  # scripts/run_build_parallel.sh.
  MY_SYMS=$(python - "$BATCH_TASK_INDEX" "${SHARDS:?}" <<'PY'
import json, sys
k, n = int(sys.argv[1]), int(sys.argv[2])
spec = json.load(open("nn_meta/artifacts_v31/baseline_spec.json"))
print(",".join(sorted(spec["symbols"])[k::n]))
PY
)
fi
echo "symbols: $MY_SYMS"

python -m nn_meta.build_meta_dataset --symbols "$MY_SYMS" --marks

# Publish this task's checkpoints (per-symbol files: disjoint across tasks).
gsutil -m -q rsync -r nn_meta/artifacts_v31/meta_rows  "${BUCKET}/out/meta_rows"
gsutil -m -q rsync -r nn_meta/artifacts_v31/meta_marks "${BUCKET}/out/meta_marks"
echo "== task done =="
