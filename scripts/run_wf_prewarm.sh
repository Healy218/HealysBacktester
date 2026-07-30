#!/usr/bin/env bash
# Parallel pre-warm of one walk-forward fold's checkpoints: freeze -> rows,
# N symbol shards each, with the same until-retry loop as run_build_parallel.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export NN_META_POOL=v31
FOLD=${1:?usage: run_wf_prewarm.sh FOLD [SHARDS]}
N=${2:-3}

run_stage(){
  local stage=$1
  local pids=()
  for k in $(seq 0 $((N-1))); do
    (
      until ./venv/bin/python scripts/wf_prewarm.py "$stage" --fold "$FOLD" --shard "$k" --of "$N" \
          >> "wf_prewarm_f${FOLD}_${stage}_s${k}.log" 2>&1; do
        echo "== $stage shard $k exited nonzero - retry in 15s ==" >> "wf_prewarm_f${FOLD}_${stage}_s${k}.log"
        sleep 15
      done
    ) &
    pids+=($!)
    sleep 5
  done
  for p in "${pids[@]}"; do wait "$p"; done
}

echo "fold $FOLD: freeze ($N shards)"
run_stage freeze
./venv/bin/python scripts/wf_prewarm.py merge-freeze --fold "$FOLD" --of "$N"
echo "fold $FOLD: rows ($N shards)"
run_stage rows
./venv/bin/python scripts/wf_prewarm.py merge-rows --fold "$FOLD" --of "$N"
echo "WF-PREWARM-FOLD${FOLD}-DONE"
