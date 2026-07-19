#!/usr/bin/env bash
# v3.1 walk-forward master: pre-warm all folds in parallel shards, then run
# the canonical walkforward_meta, which consumes the checkpoints and does
# fold dataset assembly + seed training + OOS eval + verdict.
set -uo pipefail
cd /home/mrhea/HealysBacktester
export NN_META_POOL=v31
N=${1:-3}
for FOLD in 1 2 3; do
  echo "PHASE: prewarm fold $FOLD"
  bash scripts/run_wf_prewarm.sh "$FOLD" "$N"
done
echo "PHASE: canonical walk-forward"
if ./venv/bin/python -m nn_meta.walkforward_meta --folds 3; then
  echo "WF-EXIT:0"
else
  echo "WF-EXIT:1"
fi
