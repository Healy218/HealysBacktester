#!/usr/bin/env bash
# Submit the sharded rows+marks build to Google Cloud Batch on spot VMs.
#
#   PROJECT=healys-batch REGION=us-central1 BUCKET=gs://healys-backtester \
#     bash deploy/gcp/submit.sh [SHARDS] [SYMBOLS]
#
# SHARDS defaults to 30. Passing SYMBOLS (comma list) runs the 2-symbol-style
# pilot on a single task. Every job carries maxRunDuration so a hung task
# can never bill past the cap — Batch deletes its VMs the moment tasks end.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/../.."

PROJECT=${PROJECT:?set PROJECT}
REGION=${REGION:-us-central1}
BUCKET=${BUCKET:?set BUCKET (gs://...)}
SHARDS=${1:-30}
SYMBOLS=${2:-}
# IMAGE_TAG overrides the tag when the image was built at an earlier commit
# (docs-only commits move HEAD without changing task code).
SHA=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/healys/backtester:${SHA}"

MODE=${TASK_MODE:-build}
case "$MODE" in
  evaluate) JOB_PREFIX=v4-evaluate ;;
  finalize) JOB_PREFIX=v4-finalize ;;
  spx0)     JOB_PREFIX=spx0-run ;;
  vol)      JOB_PREFIX=vol-build ;;
  assemble) JOB_PREFIX=marks-assemble ;;
  diff)     JOB_PREFIX=v4-diff ;;
  *)        JOB_PREFIX=marks-build ;;
esac
JOB="${JOB_PREFIX}-${SHA}-$(date +%H%M%S)"

if [ -n "$SYMBOLS" ]; then TASKS=1; else TASKS=$SHARDS; fi

# Training modes are a single task and want a bigger box and a longer leash than
# a per-symbol build shard: 5 seeds x 60 epochs plus a 600-estimator GBT, and for
# finalize a 40-seed persisted ensemble. Defaults below are overridable.
case "$MODE" in
  spx0)
    # build (~5 min) + nested walk-forward with 2 heads × seeds; one VM.
    TASKS=1
    MACHINE=${MACHINE:-e2-standard-8}
    CPU_MILLI=${CPU_MILLI:-8000}
    MEMORY_MIB=${MEMORY_MIB:-32768}
    MAX_RUN=${MAX_RUN:-43200s}
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  evaluate|finalize)
    TASKS=1
    MACHINE=${MACHINE:-n2-standard-8}
    CPU_MILLI=${CPU_MILLI:-8000}
    MEMORY_MIB=${MEMORY_MIB:-32768}
    MAX_RUN=${MAX_RUN:-43200s}          # 12h — training must not be killed mid-run
    # SPOT preemption would restart training from zero and these modes have no
    # per-symbol checkpointing to resume from, so pay for a STANDARD VM.
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  diff)
    # One short task. Sized generously on purpose: it loads TWO ~490k-row
    # frames into pandas and aligns them, and OOM-failing the correctness gate
    # for the sake of a few cents would be a poor trade. e2 over n2 — n2 hit
    # CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED on 2026-08-19.
    TASKS=1
    MACHINE=${MACHINE:-e2-standard-8}
    CPU_MILLI=${CPU_MILLI:-8000}
    MEMORY_MIB=${MEMORY_MIB:-24576}
    MAX_RUN=${MAX_RUN:-3600s}
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  *)
    CPU_MILLI=${CPU_MILLI:-4000}
    MEMORY_MIB=${MEMORY_MIB:-12288}
    MAX_RUN=${MAX_RUN:-14400s}
    PROVISIONING=${PROVISIONING:-SPOT}
    RETRIES=${RETRIES:-3}
    ;;
esac

# EXTRA_ARGS is interpolated into JSON; a double quote in it would break the
# document. Flag lists never need one, so refuse rather than emit invalid JSON.
case "${EXTRA_ARGS:-}" in
  *'"'*) echo "EXTRA_ARGS must not contain double quotes" >&2; exit 1 ;;
esac

cat > /tmp/healys_batch_job.json <<JSON
{
  "taskGroups": [{
    "taskCount": ${TASKS},
    "parallelism": ${PARALLEL:-${TASKS}},
    "taskSpec": {
      "runnables": [{"container": {"imageUri": "${IMAGE}"}}],
      "computeResource": {"cpuMilli": ${CPU_MILLI}, "memoryMib": ${MEMORY_MIB}},
      "maxRetryCount": ${RETRIES},
      "maxRunDuration": "${MAX_RUN}",
      "environment": {"variables": {
        "BUCKET": "${BUCKET}",
        "SHARDS": "${SHARDS}",
        "SYMBOLS": "${SYMBOLS}",
        "TASK_MODE": "${MODE}",
        "EXTRA_ARGS": "${EXTRA_ARGS:-}",
        "BASELINE_URI": "${BASELINE_URI:-}",
        "CANDIDATE_URI": "${CANDIDATE_URI:-}"
      }}
    }
  }],
  "allocationPolicy": {
    "instances": [{"policy": {
      "machineType": "${MACHINE:-e2-standard-4}",
      "provisioningModel": "${PROVISIONING}"
    }}],
    "network": {"networkInterfaces": [{
      "network": "projects/${PROJECT}/global/networks/default",
      "subnetwork": "regions/${REGION}/subnetworks/default",
      "noExternalIpAddress": true
    }]}
  },
  "logsPolicy": {"destination": "CLOUD_LOGGING"}
}
JSON

gcloud batch jobs submit "$JOB" --project "$PROJECT" --location "$REGION" \
  --config /tmp/healys_batch_job.json
echo "submitted: $JOB  (mode=$MODE machine=${MACHINE:-e2-standard-4} $PROVISIONING)"
echo "watch:     gcloud batch jobs describe $JOB --project $PROJECT --location $REGION"
case "$MODE" in
  build)
    echo "when all build tasks SUCCEED, run the single assemble task:"
    echo "  TASK_MODE=assemble PROJECT=... BUCKET=... bash deploy/gcp/submit.sh 1" ;;
  assemble)
    echo "then the ledger re-runs (these MUST NOT run on the home box — proven"
    echo "single-bit memory corruption, see HANDOFF.md):"
    echo "  TASK_MODE=evaluate EXTRA_ARGS='--ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D' \\"
    echo "    PROJECT=$PROJECT BUCKET=$BUCKET bash deploy/gcp/submit.sh 1" ;;
  evaluate)
    echo "outputs land under ${BUCKET}/out/evaluate-<UTC stamp>/ with SHA256SUMS.txt" ;;
  finalize)
    echo "outputs land under ${BUCKET}/out/finalize-<UTC stamp>/ with SHA256SUMS.txt"
    echo "rc=1 from the task means NOTHING CLEARED THE GATE — a result, not a crash;"
    echo "the reports are published either way." ;;
esac
