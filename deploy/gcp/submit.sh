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
SHA=$(git rev-parse --short HEAD)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/healys/backtester:${SHA}"
JOB="marks-build-${SHA}-$(date +%H%M%S)"

if [ -n "$SYMBOLS" ]; then TASKS=1; else TASKS=$SHARDS; fi

cat > /tmp/healys_batch_job.json <<JSON
{
  "taskGroups": [{
    "taskCount": ${TASKS},
    "parallelism": ${TASKS},
    "taskSpec": {
      "runnables": [{"container": {"imageUri": "${IMAGE}"}}],
      "computeResource": {"cpuMilli": 4000, "memoryMib": 12288},
      "maxRetryCount": 3,
      "maxRunDuration": "14400s",
      "environment": {"variables": {
        "BUCKET": "${BUCKET}",
        "SHARDS": "${SHARDS}",
        "SYMBOLS": "${SYMBOLS}",
        "TASK_MODE": "${TASK_MODE:-build}"
      }}
    }
  }],
  "allocationPolicy": {
    "instances": [{"policy": {
      "machineType": "e2-standard-4",
      "provisioningModel": "SPOT"
    }}]
  },
  "logsPolicy": {"destination": "CLOUD_LOGGING"}
}
JSON

gcloud batch jobs submit "$JOB" --project "$PROJECT" --location "$REGION" \
  --config /tmp/healys_batch_job.json
echo "submitted: $JOB"
echo "watch:     gcloud batch jobs describe $JOB --project $PROJECT --location $REGION"
echo "when all build tasks SUCCEED, run the single assemble task:"
echo "  TASK_MODE=assemble PROJECT=... BUCKET=... bash deploy/gcp/submit.sh 1"
