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

MODE="${TASK_MODE:-build}"

# The frozen spec is an input to every mode.
mkdir -p nn_meta/artifacts_v31
gsutil -m -q rsync -r "${BUCKET}/artifacts_v31_in" nn_meta/artifacts_v31

case "$MODE" in
  evaluate|finalize)
    # Training modes read the ASSEMBLED dataset, never the raw option bars, so
    # the multi-GB data_cache_v3 rsync is skipped — it is the bulk of task
    # startup and egress and nothing here reads it.
    for f in meta_dataset.parquet meta_dataset.marks.parquet; do
      gsutil -q cp "${BUCKET}/out/${f}" "nn_meta/artifacts_v31/${f}" || {
        echo "FATAL: ${BUCKET}/out/${f} missing — run TASK_MODE=assemble first" >&2
        exit 1; }
    done
    ;;
  *)
    # Stage the raw option-bar cache (read-only input) for build/assemble.
    mkdir -p nn_meta/data_cache_v3
    gsutil -m -q rsync -r "${BUCKET}/data_cache_v3" nn_meta/data_cache_v3

    # FAIL CLOSED ON AN INCOMPLETE CACHE. On 2026-08-19 the bucket was missing
    # 44 of 486 flat-file day-frames and nothing complained: FlatFilesProvider
    # returns None for an absent day, so trades spanning the gap were silently
    # unpriced and dropped. The drop was BIASED (dropped trades averaged
    # +0.017 net_return against +0.114 for survivors), so the whole ledger
    # re-run read better than the truth and had to be thrown away. Never again
    # -- a hole in the archive stops the job here, before it costs a build.
    python -m nn_meta.cache_preflight --cache nn_meta/data_cache_v3

    # Resume: pull any checkpoints previous attempts already produced.
    # gsutil rsync refuses to create the destination dir — without the mkdirs the
    # pull silently no-ops (seen live 2026-08-18: CommandException swallowed by
    # `|| true`), which would make an assemble task fold up EMPTY local dirs.
    mkdir -p nn_meta/artifacts_v31/meta_rows nn_meta/artifacts_v31/meta_marks
    gsutil -m -q rsync -r "${BUCKET}/out/meta_rows"  nn_meta/artifacts_v31/meta_rows  || true
    gsutil -m -q rsync -r "${BUCKET}/out/meta_marks" nn_meta/artifacts_v31/meta_marks || true
    ;;
esac

# ---- training modes -------------------------------------------------------
# WHY THESE RUN HERE AND NOT ON THE HOME BOX: that machine has PROVEN
# single-bit memory corruption (2026-08-18; a bit flipped r->v inside a .pyc
# the CPU was writing — evidence kept at docs/incidents/). The corruption is
# SILENT unless it happens to land somewhere that fails loudly, and these two
# steps produce the bundle that is committed and deployed to production. A flip
# in a training array or a model weight would ship a wrong model with no error.
# Full reasoning: HANDOFF.md.
if [ "$MODE" = "evaluate" ] || [ "$MODE" = "finalize" ]; then
  MARKS=nn_meta/artifacts_v31/meta_dataset.marks.parquet
  [ -f "$MARKS" ] || { echo "FATAL: $MARKS not staged" >&2; exit 1; }
  # Seconds alone are NOT unique enough. Two evaluate jobs submitted together on
  # 2026-08-19 stamped 044509Z and 044510Z — one second apart. Had their VMs come
  # up in the same second both runs would have written to the SAME directory and
  # silently clobbered each other's reports. BATCH_JOB_UID is unique per job, so
  # a suffix of it makes collision impossible regardless of start timing.
  STAMP="${MODE}-$(date -u +%Y%m%dT%H%M%SZ)-${BATCH_JOB_UID##*-}"
  STAMP="${STAMP%-}"   # tolerate BATCH_JOB_UID being unset (local/manual runs)
  OUT="${BUCKET}/out/${STAMP}"
  echo "== $MODE — publishing to ${OUT} =="
  echo "== extra args: ${EXTRA_ARGS:-<none>} =="

  # EXTRA_ARGS is deliberately unquoted: it carries a flag list that must word-split.
  set +e
  if [ "$MODE" = "evaluate" ]; then
    python -m nn_meta.v4_evaluate --marks "$MARKS" ${EXTRA_ARGS:-}
  else
    python -m nn_meta.v4_finalize --marks "$MARKS" ${EXTRA_ARGS:-}
  fi
  rc=$?
  set -e
  echo "== $MODE exited rc=$rc =="

  # Publish BEFORE honouring rc. v4_finalize exits 1 when nothing clears the
  # eligibility gate — that is a real RESULT, not a crash, and the reports that
  # explain WHY must survive it. Losing them to a non-zero exit would waste the
  # whole run.
  for pair in "nn_meta/reports_v31:reports" "nn_meta/model_final_v4:model_final_v4" \
              "nn_meta/runs_v31:runs"; do
    src=${pair%%:*}; dst=${pair##*:}
    [ -d "$src" ] || continue
    echo "publishing $src -> ${OUT}/${dst}"
    gsutil -m -q rsync -r "$src" "${OUT}/${dst}"
  done

  # Checksums: the entire point of running here is an artifact you can TRUST.
  # Hashing every output makes that checkable — a second run, on this or other
  # hardware, can be compared file for file instead of assumed identical.
  find nn_meta/reports_v31 nn_meta/model_final_v4 nn_meta/runs_v31 -type f 2>/dev/null \
    | sort | xargs -r sha256sum > /tmp/SHA256SUMS.txt || true
  gsutil -q cp /tmp/SHA256SUMS.txt "${OUT}/SHA256SUMS.txt" || true
  echo "== $MODE published; $(wc -l < /tmp/SHA256SUMS.txt 2>/dev/null || echo 0) files hashed =="
  exit $rc
fi

if [ "$MODE" = "assemble" ]; then
  # Fail closed: assembling from an empty pull must never "succeed".
  n_rows=$(find nn_meta/artifacts_v31/meta_rows -name '*.parquet' | wc -l)
  echo "assemble: $n_rows per-symbol row files pulled"
  if [ "$n_rows" -lt 1 ]; then
    echo "FATAL: resume pull produced no meta_rows — refusing to assemble" >&2
    exit 1
  fi
  ./venv/bin/python -m nn_meta.build_meta_dataset --assemble 2>/dev/null \
    || python -m nn_meta.build_meta_dataset --assemble
  # publish MUST fail the task on error — Batch reporting SUCCEEDED while the
  # VM holding the only copy self-deletes is the P1-6 failure mode
  gsutil -m -q cp nn_meta/artifacts_v31/meta_dataset.parquet "${BUCKET}/out/"
  gsutil -m -q cp nn_meta/artifacts_v31/*.marks.parquet "${BUCKET}/out/"
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

# Build and publish PER SYMBOL: a maxRunDuration kill or spot preemption
# then costs at most one in-flight symbol instead of the whole task (the
# 2026-08-17 kill-loop: 8-symbol tasks outran the 4h cap and, publishing
# only at task end, every retry restarted from zero).
IFS=',' read -ra SYMS <<< "$MY_SYMS"
for sym in "${SYMS[@]}"; do
  if gsutil -q stat "${BUCKET}/out/meta_rows/${sym}.parquet" 2>/dev/null; then
    echo "== $sym already in bucket — skip =="
    continue
  fi
  python -m nn_meta.build_meta_dataset --symbols "$sym" --marks
  gsutil -m -q rsync -r nn_meta/artifacts_v31/meta_rows  "${BUCKET}/out/meta_rows"
  gsutil -m -q rsync -r nn_meta/artifacts_v31/meta_marks "${BUCKET}/out/meta_marks"
done
echo "== task done =="
