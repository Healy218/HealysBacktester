#!/usr/bin/env bash
# Best-effort time-based cancellation monitor for explicit GCP Batch job IDs.
# At the estimated budget deadline, request cancellation and keep checking
# until every job is confirmed terminal. Unknown states remain active and
# failed cancellation requests are retried; neither implies billing stopped.
# The guard cannot enforce a hard spend cap if its host/process dies or the
# cloud API is unavailable. Billing alerts are delayed notifications only.
#
#   BUDGET_USD=25 USD_PER_HOUR=1.00 \
#     setsid nohup scripts/cloud_budget_guard.sh JOB1 JOB2 \
#     > logs/budget_guard.log 2>&1 &
#
# Set USD_PER_HOUR from the campaign's worst-case fleet rate. Its historical
# default of 1.00 is a configuration value, not a current pricing guarantee.
# Include SPENT_USD when restarting a guard partway through a campaign.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

JOBS=("$@")
[ ${#JOBS[@]} -gt 0 ] || { echo "usage: $0 JOB [JOB...]" >&2; exit 2; }
REGION=${REGION:-us-central1}
PROJECT=${PROJECT:-healys-batch}
BUDGET_USD=${BUDGET_USD:-25}
USD_PER_HOUR=${USD_PER_HOUR:-1.00}
WARN_FRACTION=${WARN_FRACTION:-0.5}
# SPENT_USD: spend that already happened BEFORE this guard started — e.g.
# when raising the budget mid-run, restart with the old guard's reported
# figure. Without it a restart silently grants a FULL fresh budget on top
# of what was already burned, which is the opposite of a brake.
SPENT_USD=${SPENT_USD:-0}

LIMIT_S=$(./venv/bin/python - "$BUDGET_USD" "$SPENT_USD" "$USD_PER_HOUR" "$WARN_FRACTION" <<'PYB'
import math, sys
budget, spent, rate, warn = map(float, sys.argv[1:])
if not all(map(math.isfinite, (budget, spent, rate, warn))) or budget < 0 or spent < 0 or rate <= 0 or not 0 <= warn <= 1:
    sys.exit("invalid budget guard inputs")
print(max(0, int((budget-spent)/rate*3600)))
PYB
) || exit 2
WARN_S=$(./venv/bin/python -c "import sys; print(int(float(sys.argv[1])*float(sys.argv[2])))" "$LIMIT_S" "$WARN_FRACTION") || exit 2
T0=$(date +%s)
echo "budget \$$BUDGET_USD at \$$USD_PER_HOUR/h -> cancellation begins after ${LIMIT_S}s ($(($LIMIT_S/3600))h)"
echo "watching: ${JOBS[*]}"

page(){ ./venv/bin/python - "$1" <<'PY'
import sys
try:
    from dotenv import load_dotenv; load_dotenv(".env")
except ImportError:
    pass
from nn_meta.live.notifier import get_notifier
get_notifier().send(sys.argv[1], title="Cloud budget guard")
PY
}

warned=0
while true; do
  ELAPSED=$(( $(date +%s) - T0 ))
  SPENT=$(./venv/bin/python -c "print(f'{$SPENT_USD+($ELAPSED/3600)*$USD_PER_HOUR:.2f}')")
  # Count only jobs still capable of billing.
  LIVE=0
  LIVE_JOBS=()
  for J in "${JOBS[@]}"; do
    ST=$(gcloud batch jobs describe "$J" --project="$PROJECT" --location="$REGION" \
           --format='value(status.state)' 2>/dev/null || echo UNKNOWN)
    case "$ST" in
      SUCCEEDED|FAILED|CANCELLED) ;;
      *) LIVE=$((LIVE+1)); LIVE_JOBS+=("$J")
         [ "$ST" != UNKNOWN ] || echo "WARNING: state unknown for $J; retaining monitoring" >&2 ;;
    esac
  done
  VMS=$(gcloud compute instances list --project="$PROJECT" --format='value(name)' 2>/dev/null | wc -l)
  ROWS=$(gsutil ls gs://healys-backtester/out/v5/meta_rows/ 2>/dev/null | wc -l)
  echo "$(date -u +%FT%TZ) elapsed=$((ELAPSED/60))m est_spend=\$$SPENT live_jobs=$LIVE vms=$VMS rows=$ROWS"

  if [ "$LIVE" -eq 0 ]; then
    echo "all jobs terminal — guard exiting (est spend \$$SPENT)"
    page "Cloud budget guard: all fleets finished on their own. Est spend \$$SPENT of \$$BUDGET_USD. rows=$ROWS/441."
    exit 0
  fi
  if [ "$warned" = 0 ] && [ "$ELAPSED" -ge "$WARN_S" ]; then
    page "Cloud budget guard: ~\$$SPENT of \$$BUDGET_USD spent (rows=$ROWS/441). Auto-cancel at \$$BUDGET_USD."
    warned=1
  fi
  if [ "$ELAPSED" -ge "$LIMIT_S" ]; then
    echo "BUDGET EXHAUSTED — cancelling ${JOBS[*]}"
    for J in "${LIVE_JOBS[@]}"; do
      gcloud batch jobs cancel "$J" --project="$PROJECT" --location="$REGION" --quiet >/dev/null 2>&1 \
        && echo "cancel requested $J" \
        || echo "ERROR: cancel failed for $J — will retry" >&2
    done
    page "Cloud budget guard: \$$BUDGET_USD budget reached — cancellation requested; monitoring until all fleets are confirmed terminal. rows=$ROWS/441."
  fi
  sleep 300
done
