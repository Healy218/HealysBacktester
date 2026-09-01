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
# A permanent describe failure (typo'd job, deleted job, revoked creds) must
# not become a silent forever-loop — this script is documented to run
# detached, where "still polling" is indistinguishable from "still running".
unknown=0
while :; do
  state=$(gcloud batch jobs describe "$JOB" --project "$PROJECT" \
            --location "$REGION" --format="value(status.state)" 2>/dev/null || echo UNKNOWN)
  case "$state" in
    SUCCEEDED|FAILED|CANCELLED) break ;;
    UNKNOWN)
      unknown=$((unknown + 1))
      echo "describe failed for $JOB — retrying ($unknown/6)"
      if [ "$unknown" -ge 6 ]; then
        echo "FATAL: $JOB undescribable after 6 attempts — giving up" >&2
        exit 2
      fi ;;
    *) unknown=0 ;;
  esac
  sleep 300
done
echo "$JOB terminal: $state"
# terminal evidence, not just metadata: the last task events
gcloud batch jobs describe "$JOB" --project "$PROJECT" --location "$REGION" \
  --format="value(status.statusEvents[].description)" 2>/dev/null \
  | tr ';' '\n' | tail -3
[ "$state" = "SUCCEEDED" ]
