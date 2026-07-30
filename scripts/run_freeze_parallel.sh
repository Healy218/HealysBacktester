#!/usr/bin/env bash
# Parallel v3.1 freeze: 2 symbol shards (memory caps the home box at 2), each
# checkpointed per-symbol and wrapped in a resume-loop — an OOM or reboot just
# resumes from the shard's spec instead of losing progress. Merge at the end.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export NN_META_POOL=v31

pkill -f 'nn_meta.freeze_baseline' 2>/dev/null || true
sleep 2
mkdir -p nn_meta/artifacts_v31

N=${1:-2}
./venv/bin/python - "$N" <<'PY'
import json, sys
n = int(sys.argv[1])
u = json.load(open('v3/artifacts/universe_120.json'))
for k in range(n):
    open(f'/tmp/fshard_{k}.txt', 'w').write(','.join(u[k::n]))   # round-robin
print(f'sharded {len(u)} symbols into {n}')
PY

run_shard(){
  local k=$1 syms
  syms=$(cat /tmp/fshard_$k.txt)
  local tries=0
  until ./venv/bin/python -m nn_meta.freeze_baseline \
      --symbols "$syms" \
      --out nn_meta/artifacts_v31/spec_shard_$k.json >> v31_freeze_$k.log 2>&1; do
    tries=$((tries+1))
    echo "== shard $k exited nonzero (try $tries) — resuming in 15s ==" \
      >> v31_freeze_$k.log
    sleep 15
  done
  echo "== shard $k COMPLETE ==" >> v31_freeze_$k.log
}

pids=()
for k in $(seq 0 $((N-1))); do
  run_shard "$k" & pids+=($!)
  echo "launched shard $k (pid $!)"
  sleep 20                      # stagger starts so both don't peak-load together
done
for p in "${pids[@]}"; do wait "$p"; done

SHARDS=$(for k in $(seq 0 $((N-1))); do
  printf 'nn_meta/artifacts_v31/spec_shard_%s.json,' "$k"; done | sed 's/,$//')
./venv/bin/python -m nn_meta.freeze_baseline --merge "$SHARDS"
echo "PARALLEL-FREEZE-DONE"
