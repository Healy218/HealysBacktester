#!/usr/bin/env bash
# Current admitted input bindings; supply new path/index/output receipts per run.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
if [[ $# -ne 3 ]]; then
    echo "Usage: $0 PATH_RECEIPT QUOTE_INDEX NEW_OUTPUT" >&2
    exit 2
fi
exec ./venv/bin/python scripts/run_v7_integrated_execution.py \
    --paths "$1" --quotes "$2" --output "$3" \
    --hours nn_meta/validation/v7-dated-hours-20260927 \
    --calendar nn_meta/data_v7/dividend-calendar-20260918/calendar.json \
    --settlement nn_meta/data_v7/dividend-calendar-20260918/settlement_calendar.json \
    --cash-events nn_meta/validation/v7-dividends-complete-20260918/events.json \
    --splits nn_meta/validation/v7-dividends-complete-20260918/actions.json \
    --renames nn_meta/validation/v7-common-share-renames-20260917/events.json \
    --boundaries nn_meta/validation/v7-noncash-admission-20260918 \
    --blackouts nn_meta/validation/v7-contract-blackouts-20260927 \
    --references nn_meta/data_v7/entry-joined-sample-references-20260926 \
    --stock-capture nn_meta/data_v7/stock-quotes-pilot-20260916/6a13b036cf269e72be05fe912713804d8bab3614249b0e4dc661901feadfe16e \
    --stock-capture nn_meta/data_v7/split-stock-quotes-20260917/7e9657dd9327f1490607390d3afe21171d1d901b0b56372393176a8124c269b4 \
    --stock-capture nn_meta/data_v7/split-stock-quotes-20260917/222f0bca5200c35d81e3e577815fb7b2595e60d41d5bfc37ee1a139756d1c8b9 \
    --through 2026-09-14
