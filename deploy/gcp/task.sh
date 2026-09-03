#!/usr/bin/env bash
# One Batch task = one symbol shard of the dataset/marks build.
#
# Env (set by the job template / submit.sh):
#   BUCKET       gs://... bucket holding data_cache_v3/ and receiving outputs
#   TASK_MODE    "build" (default) — per-symbol rows+marks; "assemble" — final
#                dataset; "diff" — the verification gate; "evaluate"/"finalize"
#   BASELINE_URI diff mode only: gs:// path to the baseline dataset
#   CANDIDATE_URI diff mode only: defaults to ${BUCKET}/out/meta_dataset.parquet
#   SHARDS       total task count (BATCH_TASK_COUNT also works)
#   SYMBOLS      optional explicit comma list (pilot runs); overrides sharding
#
# Batch injects BATCH_TASK_INDEX. Everything is resume-safe: outputs are the
# same per-symbol checkpoints the local pipeline writes, synced to the bucket,
# so a preempted-and-retried task skips finished symbols.
set -euo pipefail
cd /app

# Local/manual runs have no Batch env; default it BEFORE any ${BATCH_JOB_UID##*-}
# expansion, which errors under nounset when the variable is unset entirely.
BATCH_JOB_UID="${BATCH_JOB_UID:-}"
# Empty operator overrides must not clobber task.sh defaults below.
[ -n "${BASELINE_URI:-}" ] || unset BASELINE_URI
[ -n "${CANDIDATE_URI:-}" ] || unset CANDIDATE_URI

echo "== task ${BATCH_TASK_INDEX:-?}/${SHARDS:-?} mode=${TASK_MODE:-build} pool=${NN_META_POOL:-v31} =="

MODE="${TASK_MODE:-build}"

# Pool selects every path (nn_meta/config.py): v31 reads data_cache_v3 (the
# historical irregular name), later pools read data_cache_<pool>.
POOL="${NN_META_POOL:-v31}"
export NN_META_POOL="$POOL"
ART="nn_meta/artifacts_${POOL}"
CACHE="data_cache_v3"; [ "$POOL" != "v31" ] && CACHE="data_cache_${POOL}"
# Non-v31 pools publish under out/<pool>/. The unsuffixed out/ names ARE
# v31's live artifacts (118 meta_rows files + the assembled dataset): a later
# pool skip-checking or publishing there would silently mix generations —
# the same wrong-directory failure NN_META_POOL exists to prevent.
OUTB="${BUCKET}/out"; [ "$POOL" != "v31" ] && OUTB="${BUCKET}/out/${POOL}"

# The frozen spec is an input to every mode EXCEPT freeze, which creates it.
if [ "$MODE" != "freeze" ] && [ "$MODE" != "freeze-merge" ]; then
  mkdir -p "$ART"
  gsutil -m -q rsync -r "${BUCKET}/artifacts_${POOL}_in" "$ART"
fi

case "$MODE" in
  evaluate|finalize)
    # Training modes read the ASSEMBLED dataset, never the raw option bars, so
    # the multi-GB data_cache_v3 rsync is skipped — it is the bulk of task
    # startup and egress and nothing here reads it.
    for f in meta_dataset.parquet meta_dataset.marks.parquet; do
      gsutil -q cp "${OUTB}/${f}" "${ART}/${f}" || {
        echo "FATAL: ${OUTB}/${f} missing — run TASK_MODE=assemble first" >&2
        exit 1; }
    done
    ;;
  vol)
    # vol-regime track stage 1 (docs/specs/VOL_SPEC.md): per-symbol RV
    # features + baseline eval from the 9y 1m crawl. Sharded by symbol,
    # resume-safe: published symbols are pulled first and skipped.
    mkdir -p v3/data/underlying nn_meta/artifacts_vol/features
    gsutil -m -q rsync -r "${BUCKET}/underlying_1m_9y" v3/data/underlying
    n=$(ls -d v3/data/underlying/*/ 2>/dev/null | wc -l)
    [ "$n" -ge 280 ] || { echo "FATAL: underlying crawl incomplete ($n symbols)" >&2; exit 1; }
    gsutil -m -q rsync -r "${BUCKET}/out/vol_features" nn_meta/artifacts_vol/features || true
    ;;
  spx0)
    # spx0 pool (docs/specs/SPX0_SPEC.md): build the 0DTE dataset from the
    # 1m index archive + proxy underlying, then the nested walk-forward. The
    # archive is ~850 MB (500 day-files + SPY/QQQ 1m), staged read-only.
    mkdir -p nn_meta/data_cache_spx0
    gsutil -m -q rsync -r "${BUCKET}/data_cache_spx0" nn_meta/data_cache_spx0
    n=$(ls nn_meta/data_cache_spx0/flatfiles_1m/*.parquet 2>/dev/null | wc -l)
    [ "$n" -ge 500 ] || { echo "FATAL: spx0 archive incomplete ($n day-files, expected 500)" >&2; exit 1; }
    for f in SPY QQQ; do
      [ -f "nn_meta/data_cache_spx0/underlying_1m/${f}.parquet" ] || {
        echo "FATAL: proxy underlying ${f} missing" >&2; exit 1; }
    done
    ;;
  diff)
    # The verification gate reads two ASSEMBLED datasets and nothing else — no
    # option-bar cache, no marks — so the multi-GB rsync is skipped entirely.
    BASELINE_URI="${BASELINE_URI:-${BUCKET}/out/stage0-baseline-2026-07-21/meta_dataset.parquet}"
    CANDIDATE_URI="${CANDIDATE_URI:-${OUTB}/meta_dataset.parquet}"
    gsutil -q cp "$BASELINE_URI" "$ART/baseline.parquet" || {
      echo "FATAL: baseline $BASELINE_URI missing" >&2; exit 1; }
    gsutil -q cp "$CANDIDATE_URI" "$ART/candidate.parquet" || {
      echo "FATAL: candidate $CANDIDATE_URI missing — run TASK_MODE=assemble first" >&2
      exit 1; }
    ;;
  freeze-merge)
    # Stages NOTHING: the handler below pulls ~450 small JSON specs itself.
    # It used to fall through to *) and drag down the multi-GB option cache
    # plus every meta_rows/meta_marks shard — on an e2-standard-4 with a
    # 30GB boot disk and a 1h leash, which is how a merge task ENOSPCs or
    # times out instead of doing five seconds of JSON work.
    :
    ;;
  *)
    # Stage the raw option-bar cache (read-only input) for freeze/build/assemble.
    # When the job mounts a local-SSD scratch volume at /mnt/ssd (fleet v3+),
    # all packed tasks on a VM SHARE one cache copy there: the first task
    # stages it at NVMe speed under an exclusive flock, the rest fast-path
    # through the same lock. Without the mount, each task stages its own
    # copy into the container layer (the 2026-08-30 lesson: 5x10GB copies
    # through a small pd disk cost ~1.4h of every slot cycle).
    if [ -d /mnt/ssd ]; then
      mkdir -p "/mnt/ssd/${CACHE}"
      rm -rf "nn_meta/${CACHE}"
      ln -sfn "/mnt/ssd/${CACHE}" "nn_meta/${CACHE}"
      flock /mnt/ssd/.stage.lock \
        gsutil -m -q rsync -r "${BUCKET}/${CACHE}" "/mnt/ssd/${CACHE}"
    else
      mkdir -p "nn_meta/${CACHE}"
      gsutil -m -q rsync -r "${BUCKET}/${CACHE}" "nn_meta/${CACHE}"
    fi

    # FAIL CLOSED ON AN INCOMPLETE CACHE. On 2026-08-19 the bucket was missing
    # 44 of 486 flat-file day-frames and nothing complained: FlatFilesProvider
    # returns None for an absent day, so trades spanning the gap were silently
    # unpriced and dropped. The drop was BIASED (dropped trades averaged
    # +0.017 net_return against +0.114 for survivors), so the whole ledger
    # re-run read better than the truth and had to be thrown away. Never again
    # -- a hole in the archive stops the job here, before it costs a build.
    python -m nn_meta.cache_preflight --cache "nn_meta/${CACHE}"

    if [ "$MODE" = "freeze" ]; then
      : # freeze needs only the cache; checkpoints are per-symbol in the bucket
    else
      # Resume: pull any checkpoints previous attempts already produced.
      # gsutil rsync refuses to create the destination dir — without the mkdirs the
      # pull silently no-ops (seen live 2026-08-18: CommandException swallowed by
      # `|| true`), which would make an assemble task fold up EMPTY local dirs.
      mkdir -p "$ART/meta_rows" "$ART/meta_marks"
      gsutil -m -q rsync -r "${OUTB}/meta_rows"  "$ART/meta_rows"  || true
      gsutil -m -q rsync -r "${OUTB}/meta_marks" "$ART/meta_marks" || true
    fi
    ;;
esac

# ---- freeze: per-symbol baseline sweeps, sharded (v5: one ticker per task) --
if [ "$MODE" = "freeze" ]; then
  if [ -n "${SYMBOLS:-}" ]; then
    MY_SYMS="$SYMBOLS"
  else
    # Round-robin shard k of N over the pool's universe (config.UNDERLYINGS —
    # for v5 that is the union of the frozen PIT monthlies, baked in the image).
    MY_SYMS=$(python - "$BATCH_TASK_INDEX" "${SHARDS:?}" <<'PY'
import sys
from nn_meta import config
k, n = int(sys.argv[1]), int(sys.argv[2])
print(",".join(sorted(config.UNDERLYINGS)[k::n]))
PY
)
  fi
  echo "freeze symbols: $MY_SYMS"
  SPECS="${BUCKET}/out/freeze_specs_${POOL}"
  mkdir -p "$ART"
  rc_all=0
  IFS=',' read -ra SYMS <<< "$MY_SYMS"
  for sym in "${SYMS[@]}"; do
    if gsutil -q stat "${SPECS}/${sym}.json" 2>/dev/null; then
      echo "== $sym already frozen in bucket — skip =="
      continue
    fi
    # A symbol too thin to freeze is a RESULT (freeze_all skips it); only a
    # crash should fail the task.
    if python -m nn_meta.freeze_baseline --symbols "$sym" \
        --out "$ART/freeze_${sym}.json"; then
      gsutil -q cp "$ART/freeze_${sym}.json" "${SPECS}/${sym}.json"
    else
      echo "== $sym freeze CRASHED ==" >&2; rc_all=1
    fi
  done
  exit $rc_all
fi

if [ "$MODE" = "freeze-merge" ]; then
  mkdir -p /tmp/fspecs "$ART"
  gsutil -m -q rsync -r "${BUCKET}/out/freeze_specs_${POOL}" /tmp/fspecs
  n=$(ls /tmp/fspecs/*.json 2>/dev/null | wc -l)
  echo "freeze-merge: $n per-symbol specs pulled"
  [ "$n" -ge 1 ] || { echo "FATAL: no freeze specs to merge" >&2; exit 1; }
  python -m nn_meta.freeze_baseline \
    --merge "$(ls /tmp/fspecs/*.json | paste -sd, -)"
  # Publish as the pool's spec input — every later mode stages it from there.
  gsutil -q cp "$ART/baseline_spec.json" \
    "${BUCKET}/artifacts_${POOL}_in/baseline_spec.json"
  echo "== merged spec published to ${BUCKET}/artifacts_${POOL}_in/ =="
  exit 0
fi

# ---- vol: sharded per-symbol RV features + baseline eval --------------------
if [ "$MODE" = "vol" ]; then
  IDX="${BATCH_TASK_INDEX:-0}"
  N="${SHARDS:-1}"
  SYMS=$(ls v3/data/underlying | awk -v n="$N" -v i="$IDX" 'NR % n == i' | paste -sd, -)
  echo "== vol shard ${IDX}/${N}: $(echo "$SYMS" | tr ',' '\n' | wc -l) symbols =="
  set +e
  python -m nn_meta.vol_features --symbols "$SYMS" --skip-existing \
    --out nn_meta/artifacts_vol
  rc=$?
  set -e
  # publish per-symbol features (shared dir, per-symbol files: shard-safe)
  gsutil -m -q rsync -r nn_meta/artifacts_vol/features "${BUCKET}/out/vol_features"
  if [ -f nn_meta/artifacts_vol/baseline_eval.parquet ]; then
    gsutil -q cp nn_meta/artifacts_vol/baseline_eval.parquet \
      "${BUCKET}/out/vol_eval/eval_shard_${IDX}.parquet"
  fi
  echo "== vol shard ${IDX} exited rc=$rc =="
  exit $rc
fi

# ---- spx0: build + evaluate in one task -------------------------------------
if [ "$MODE" = "spx0" ]; then
  STAMP="spx0-$(date -u +%Y%m%dT%H%M%SZ)-${BATCH_JOB_UID##*-}"; STAMP="${STAMP%-}"
  OUT="${BUCKET}/out/${STAMP}"
  echo "== spx0 — publishing to ${OUT} =="
  echo "== extra args: ${EXTRA_ARGS:-<none>} =="
  set +e
  python -m nn_meta.spx0.build_dataset --out nn_meta/artifacts_spx0 \
    && python -m nn_meta.spx0.evaluate --dataset nn_meta/artifacts_spx0/meta_dataset.parquet \
         --output nn_meta/artifacts_spx0/reports/spx0_walkforward_report.md ${EXTRA_ARGS:-}
  rc=$?
  set -e
  echo "== spx0 exited rc=$rc =="
  if [ -d nn_meta/artifacts_spx0 ]; then
    gsutil -m -q rsync -r nn_meta/artifacts_spx0 "${OUT}/artifacts_spx0"
    find nn_meta/artifacts_spx0 -type f | sort | xargs -r sha256sum > /tmp/SHA256SUMS.txt || true
    gsutil -q cp /tmp/SHA256SUMS.txt "${OUT}/SHA256SUMS.txt" || true
  fi
  echo "== spx0 published =="
  exit $rc
fi

# ---- training modes -------------------------------------------------------
# HISTORICAL DOCTRINE, SUPERSEDED 2026-09-03 — READ BEFORE RE-APPLYING IT.
# This block used to say training must NEVER run on the home box, because
# that machine had PROVEN single-bit memory corruption (2026-08-18; a bit
# flipped r->v inside a .pyc the CPU was writing — evidence still kept at
# docs/incidents/). That reasoning was sound for the hardware it was written
# about: the i5-11400/B560 build with the faulty RAM. **That machine was
# RETIRED 2026-08-23** and replaced by the Ryzen 9850X3D / new DDR5 box, so
# the premise no longer holds and the rule no longer binds.
# Current doctrine (user decision 2026-09-03, docs/DECISIONS.md): assemble
# and training MAY run on the home box; cloud is optional, not required.
# The concern that survives the hardware swap is that the NEW RAM is
# unvalidated, and these steps still produce the bundle that gets committed
# and deployed to production — so validate by DETERMINISM, not by absence of
# a crash: run evaluate twice with identical seeds and diff the
# SHA256SUMS.txt this code already writes. Byte-identical = no silent flip.
# These modes remain fully supported here for when cloud is the better tool.
if [ "$MODE" = "evaluate" ] || [ "$MODE" = "finalize" ]; then
  MARKS="$ART/meta_dataset.marks.parquet"
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
  # reports/runs are pool-suffixed (config._SUF); model_final_v4 is the fixed
  # v4_finalize bundle dir regardless of pool (v4_finalize.py FINAL_DIR).
  for pair in "nn_meta/reports_${POOL}:reports" "nn_meta/model_final_v4:model_final_v4" \
              "nn_meta/runs_${POOL}:runs"; do
    src=${pair%%:*}; dst=${pair##*:}
    [ -d "$src" ] || continue
    echo "publishing $src -> ${OUT}/${dst}"
    gsutil -m -q rsync -r "$src" "${OUT}/${dst}"
  done

  # Checksums: the entire point of running here is an artifact you can TRUST.
  # Hashing every output makes that checkable — a second run, on this or other
  # hardware, can be compared file for file instead of assumed identical.
  find "nn_meta/reports_${POOL}" nn_meta/model_final_v4 "nn_meta/runs_${POOL}" -type f 2>/dev/null \
    | sort | xargs -r sha256sum > /tmp/SHA256SUMS.txt || true
  gsutil -q cp /tmp/SHA256SUMS.txt "${OUT}/SHA256SUMS.txt" || true
  echo "== $MODE published; $(wc -l < /tmp/SHA256SUMS.txt 2>/dev/null || echo 0) files hashed =="
  exit $rc
fi

# ---- the verification gate ------------------------------------------------
# Runs HERE and not on the home box for the SAME reason as the training modes:
# a flipped bit in either frame would produce a confident WRONG verdict, and
# this gate is precisely what decides whether the rebuilt dataset can be
# trusted. Verifying trustworthiness on untrustworthy hardware is circular.
if [ "$MODE" = "diff" ]; then
  STAMP="diff-$(date -u +%Y%m%dT%H%M%SZ)-${BATCH_JOB_UID##*-}"
  STAMP="${STAMP%-}"   # tolerate BATCH_JOB_UID being unset (local/manual runs)
  OUT="${BUCKET}/out/${STAMP}"
  echo "== diff — publishing to ${OUT} =="
  mkdir -p /tmp/diff

  # --expect-identical is what makes this a GATE rather than a report: any
  # surviving difference exits 1. The rebuild is only done when the 13 columns
  # collapse to zero. EXTRA_ARGS is unquoted so a flag list word-splits.
  set +e
  python -m nn_meta.dataset_diff \
    --baseline  "$ART/baseline.parquet" \
    --candidate "$ART/candidate.parquet" \
    --expect-identical ${EXTRA_ARGS:-} 2>&1 | tee /tmp/diff/dataset_diff.txt
  rc=${PIPESTATUS[0]}
  set -e
  echo "== diff exited rc=$rc =="

  # Publish BEFORE honouring rc. A FAILING gate is exactly the result whose
  # evidence must survive — same doctrine as the training modes.
  {
    echo
    echo "# inputs"
    echo "# baseline : $BASELINE_URI"
    echo "# candidate: $CANDIDATE_URI"
    sha256sum "$ART/baseline.parquet" \
              "$ART/candidate.parquet"
  } >> /tmp/diff/dataset_diff.txt || true
  find /tmp/diff -type f | sort | xargs -r sha256sum > /tmp/SHA256SUMS.txt || true
  gsutil -m -q rsync -r /tmp/diff "${OUT}" || true
  gsutil -q cp /tmp/SHA256SUMS.txt "${OUT}/SHA256SUMS.txt" || true
  echo "== diff published to ${OUT} =="
  exit $rc
fi

if [ "$MODE" = "assemble" ]; then
  # Fail closed: assembling from an empty pull must never "succeed".
  n_rows=$(find "$ART/meta_rows" -name '*.parquet' | wc -l)
  echo "assemble: $n_rows per-symbol row files pulled"
  if [ "$n_rows" -lt 1 ]; then
    echo "FATAL: resume pull produced no meta_rows — refusing to assemble" >&2
    exit 1
  fi
  ./venv/bin/python -m nn_meta.build_meta_dataset --assemble 2>/dev/null \
    || python -m nn_meta.build_meta_dataset --assemble
  # publish MUST fail the task on error — Batch reporting SUCCEEDED while the
  # VM holding the only copy self-deletes is the P1-6 failure mode
  gsutil -m -q cp "$ART/meta_dataset.parquet" "${OUTB}/"
  gsutil -m -q cp "$ART"/*.marks.parquet "${OUTB}/"
  exit 0
fi

if [ -n "${SYMBOLS:-}" ]; then
  MY_SYMS="$SYMBOLS"
else
  # Round-robin shard k of N over the frozen spec — same split rule as
  # scripts/run_build_parallel.sh.
  MY_SYMS=$(python - "$BATCH_TASK_INDEX" "${SHARDS:?}" <<'PY'
import json, sys
from nn_meta import config
k, n = int(sys.argv[1]), int(sys.argv[2])
spec = json.load(open(config.BASELINE_SPEC_JSON))
print(",".join(sorted(spec["symbols"])[k::n]))
PY
)
fi
echo "symbols: $MY_SYMS"

# Build and publish PER SYMBOL: a maxRunDuration kill or spot preemption
# then costs at most one in-flight symbol instead of the whole task (the
# 2026-08-17 kill-loop: 8-symbol tasks outran the 4h cap and, publishing
# only at task end, every retry restarted from zero).
# Per-family partials (2026-09-01): a v5 symbol is ~8h of work and spot
# preemption used to lose all of it. build_meta_dataset --partial-dir writes
# a checkpoint per completed family; a background loop pushes them to the
# bucket every 4 min so a preempted retry loses at most one family in
# flight. Pull is per-symbol so a task never drags the whole fleet's
# partials.
PART="$ART/meta_partial"
mkdir -p "$PART"
( while sleep 240; do
    gsutil -m -q rsync -r "$PART" "${OUTB}/meta_partial" 2>/dev/null || true
  done ) &
PART_SYNC=$!
trap 'kill $PART_SYNC 2>/dev/null || true' EXIT

IFS=',' read -ra SYMS <<< "$MY_SYMS"
for sym in "${SYMS[@]}"; do
  if gsutil -q stat "${OUTB}/meta_rows/${sym}.parquet" 2>/dev/null; then
    echo "== $sym already in bucket — skip =="
    continue
  fi
  gsutil -m -q cp "${OUTB}/meta_partial/${sym}.*" "$PART/" 2>/dev/null || true
  python -m nn_meta.build_meta_dataset --symbols "$sym" --marks \
    --partial-dir "$PART"
  gsutil -m -q rsync -r "$ART/meta_rows"  "${OUTB}/meta_rows"
  gsutil -m -q rsync -r "$ART/meta_marks" "${OUTB}/meta_marks"
done
echo "== task done =="
