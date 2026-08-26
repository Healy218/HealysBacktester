#!/usr/bin/env bash
# Poll ONE explicit Batch job to a terminal state and print the evidence.
#
#   bash deploy/gcp/watch_job.sh [JOB]        # default: deploy/gcp/.last_job
#
# Discipline (2026-08-25, after two stale-watcher incidents): a watcher BINDS
# to an ID captured at submit time. It never lists-and-picks — a list sorted
# wrong, or a job submitted in between, silently watches the wrong thing and
# reports a stale state with full confidence.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/../.."
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

PROJECT=${PROJECT:-healys-batch}
REGION=${REGION:-us-central1}
JOB="${1:-$(cat deploy/gcp/.last_job 2>/dev/null || true)}"
[ -n "$JOB" ] || { echo "no JOB given and no deploy/gcp/.last_job" >&2; exit 1; }

echo "watching $JOB (poll 300s)"
while :; do
  state=$(gcloud batch jobs describe "$JOB" --project "$PROJECT" \
            --location "$REGION" --format="value(status.state)" 2>/dev/null || echo UNKNOWN)
  case "$state" in
    SUCCEEDED|FAILED|CANCELLED) break ;;
    UNKNOWN) echo "describe failed for $JOB — retrying" ;;
  esac
  sleep 300
done
echo "$JOB terminal: $state"
# terminal evidence, not just metadata: the last task events
gcloud batch jobs describe "$JOB" --project "$PROJECT" --location "$REGION" \
  --format="value(status.statusEvents[].description)" 2>/dev/null \
  | tr ';' '\n' | tail -3
[ "$state" = "SUCCEEDED" ]
