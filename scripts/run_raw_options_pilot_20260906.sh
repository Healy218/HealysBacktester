#!/usr/bin/env bash
# Dated, isolated raw-options pilot; execution remains inside the validated launcher.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

pilot_marker="${JOB_EXIT_MARKER:-scripts/.jobstate/raw_options_pilot_20260906.exit}"
mkdir -p scripts/.jobstate "$(dirname "$pilot_marker")"
# Acquire the wrapper lock BEFORE truncating the marker or installing its exit
# writer. A duplicate invocation must not erase the active run's state.
exec {pilot_lock_fd}>scripts/.jobstate/raw_options_pilot_20260906.lock
if ! flock -n "$pilot_lock_fd"; then
    printf '%s\n' 'raw-options pilot already has a running wrapper' >&2
    exit 75
fi
pilot_finish() {
    local pilot_exit_code=$?
    trap - EXIT
    printf '%s\n' "$pilot_exit_code" > "$pilot_marker"
    exit "$pilot_exit_code"
}
trap pilot_finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
: > "$pilot_marker"

. scripts/lib/autosize.sh
pilot_symbols=SPY,IBKR
IFS=, read -r -a pilot_symbol_list <<< "$pilot_symbols"
# autosize uses MiB; 5120 MiB = 5 GiB per worker, plus its shared reserve.
pilot_workers=$(autosize_workers 5120)
if (( pilot_workers > ${#pilot_symbol_list[@]} )); then
    pilot_workers=${#pilot_symbol_list[@]}
fi
autosize_report raw-options-20260906-r2-pilot "$pilot_workers"
export NN_META_DATA_CANDIDATE=audit-repair-20260905-final
export PYTHONDONTWRITEBYTECODE=1
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/healys-plan-numba}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/healys-plan-mpl}"

bash scripts/run_research_local.sh \
    --campaign raw-options-20260906-r2 --pool v6 \
    --stage freeze --stage build --stage assemble \
    --symbols "$pilot_symbols" --workers "$pilot_workers" --run
