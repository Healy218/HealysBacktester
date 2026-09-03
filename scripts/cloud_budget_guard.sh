#!/usr/bin/env bash
# HARD spend stop for GCP Batch fleets. Runs detached; cancels the named jobs
# when the time budget is exhausted, then pages Telegram.
#
# WHY THIS EXISTS: a GCP "budget" does NOT cap spending — it only emails when
# a threshold is crossed. There is no native spend limit. On a PAID billing
# account (this project since 2026-08-27), exhausting credits means the card
# is charged, silently. On 2026-09-02 the campaign had burned $263 of $300
# before anyone did the burn-rate × duration multiplication. This script is
# the brake that GCP does not provide.
#
# The budget is expressed in TIME because that is what we can measure locally
# and in real time: console billing lags 1-2 days, and no API exposes credit
# balance. Convert with the worst-case rate, never the average one.
#
#   BUDGET_USD=25 USD_PER_HOUR=1.00 \
#     setsid nohup scripts/cloud_budget_guard.sh JOB1 JOB2 \
#     > logs/budget_guard.log 2>&1 &
#
# USD_PER_HOUR default 1.00 = 4 x (n2|c2d)-highmem-8 SPOT + 375GB local SSD
# + boot disk, rounded UP. Rounding up is the point: an early cancel costs a
# rerun, a late one costs money you do not have.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

JOBS=("$@")
[ ${#JOBS[@]} -gt 0 ] || { echo "usage: $0 JOB [JOB...]" >&2; exit 2; }
REGION=${REGION:-us-central1}
BUDGET_USD=${BUDGET_USD:-25}
USD_PER_HOUR=${USD_PER_HOUR:-1.00}
WARN_FRACTION=${WARN_FRACTION:-0.5}
# SPENT_USD: spend that already happened BEFORE this guard started — e.g.
# when raising the budget mid-run, restart with the old guard's reported
# figure. Without it a restart silently grants a FULL fresh budget on top
# of what was already burned, which is the opposite of a brake.
SPENT_USD=${SPENT_USD:-0}

LIMIT_S=$(./venv/bin/python -c "print(max(0, int((($BUDGET_USD-$SPENT_USD)/$USD_PER_HOUR)*3600)))")
WARN_S=$(./venv/bin/python -c "print(int($LIMIT_S*$WARN_FRACTION))")
T0=$(date +%s)
echo "budget \$$BUDGET_USD at \$$USD_PER_HOUR/h -> hard cancel after ${LIMIT_S}s ($(($LIMIT_S/3600))h)"
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
  for J in "${JOBS[@]}"; do
    ST=$(gcloud batch jobs describe "$J" --location="$REGION" \
           --format='value(status.state)' 2>/dev/null || echo GONE)
    case "$ST" in SUCCEEDED|FAILED|CANCELLED|GONE) ;; *) LIVE=$((LIVE+1)) ;; esac
  done
  VMS=$(gcloud compute instances list --format='value(name)' 2>/dev/null | wc -l)
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
    for J in "${JOBS[@]}"; do
      gcloud batch jobs cancel "$J" --location="$REGION" --quiet >/dev/null 2>&1 \
        && echo "cancelled $J"
    done
    page "Cloud budget guard: \$$BUDGET_USD budget reached — fleets CANCELLED at rows=$ROWS/441. Home box keeps building for free."
    exit 0
  fi
  sleep 300
done
