#!/usr/bin/env bash
# Continue the September 30 reconciled frontier using unchanged bound producers.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source scripts/lib/autosize.sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
py="$PWD/venv/bin/python"
case "${1:-}" in
  quotes)
    workers=$(autosize_workers 1024 16384)
    (( workers <= 2 )) || workers=2
    autosize_report 'V7 September 30 actual quote frontier' "$workers"
    exec "$py" -u scripts/capture_v7_recovery_frontier.py capture \
      --plan nn_meta/validation/v7-recovery-frontier-20260930-r0 \
      --previous-index nn_meta/validation/v7-frontier-quote-index-20260929-evening-r0 \
      --output nn_meta/data_v7/execution-recovery-20260930-r0 \
      --state nn_meta/validation/v7-frontier-capture-20260930-r0 \
      --index-output nn_meta/validation/v7-frontier-quote-index-20260930-r0 \
      --workers "$workers" --max-seconds 21600
    ;;
  references)
    workers=$(autosize_workers 64 16384)
    (( workers <= 4 )) || workers=4
    autosize_report 'V7 September 30 actual held references' "$workers"
    "$py" -u scripts/run_v7_reference_campaign.py \
      --plan nn_meta/validation/v7-held-reference-demand-20260930-r0 \
      --output nn_meta/data_v7/held-reference-campaign-20260930-r0 \
      --state nn_meta/validation/v7-held-reference-campaign-20260930-r0 \
      --workers "$workers"
    exec "$py" scripts/audit_v7_reference_campaign_v2.py \
      --campaign nn_meta/validation/v7-held-reference-campaign-20260930-r0 \
      --blackouts nn_meta/validation/v7-contract-blackouts-20260929-held-approved \
      --output nn_meta/validation/v7-held-reference-reconciliation-20260930-r0
    ;;
  discovery)
    workers=$(autosize_workers 2048 16384)
    (( workers <= 1 )) || workers=1
    autosize_report 'V7 original full-universe discovery continuation' "$workers"
    exec "$py" -u scripts/run_v7_execution_recovery.py \
      --plan nn_meta/validation/v7-full-execution-plan-20260928 \
      --base-index nn_meta/validation/v7-frontier-quote-index-20260928-r4 \
      --entry-root nn_meta/data_v7/entry-campaign-20260927 \
      --references nn_meta/validation/v7-reference-reconciliation-20260928-full-r0 \
      --review nn_meta/validation/v7-reference-rename-review-20260928 \
      --hours nn_meta/validation/v7-dated-hours-20260927 \
      --blackouts nn_meta/validation/v7-contract-blackouts-20260928-approved \
      --parent-state nn_meta/validation/v7-execution-campaign-20260928-r1 \
      --state nn_meta/validation/v7-execution-recovery-20260929-r0 \
      --workers "$workers" --slice-seconds 300 --max-seconds 21600
    ;;
  *) echo 'Usage: continue_v7_inputs_20260930.sh quotes|references|discovery' >&2; exit 2 ;;
esac
