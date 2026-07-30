#!/usr/bin/env bash
# v3.1 walk-forward master: pre-warm all folds in parallel shards, then run
# the canonical walkforward_meta, which consumes the checkpoints and does
# fold dataset assembly + seed training + OOS eval + verdict.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export NN_META_POOL=v31
N=${1:-3}

# See run_v4_finalize.sh: create the marker empty at start so an interrupted
# run is auto-restartable, and so a job nobody launched here stays untouched.
MARKER="${JOB_EXIT_MARKER:-scripts/.jobstate/v31_walkforward.exit}"
mkdir -p "$(dirname "$MARKER")" && : > "$MARKER"
for FOLD in 1 2 3; do
  echo "PHASE: prewarm fold $FOLD"
  bash scripts/run_wf_prewarm.sh "$FOLD" "$N"
done
echo "PHASE: canonical walk-forward"
if ./venv/bin/python -m nn_meta.walkforward_meta --folds 3; then
  WF_EXIT=0
else
  WF_EXIT=1
fi
echo "WF-EXIT:$WF_EXIT"
# Per-run exit marker for scripts/boot_restart.sh (0 => done, else => retry).
# Replaces the descriptor's `grep WF-EXIT:0 v31_wf.log` done-check, which read
# a gitignored append-only log — stale forever across re-runs, and absent
# entirely on a restored box.
echo "$WF_EXIT" > "$MARKER" 2>/dev/null || true
