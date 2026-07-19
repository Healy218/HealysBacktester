#!/usr/bin/env bash
# Parallel v3.1 dataset build: N symbol shards writing per-symbol rows to a
# shared meta_rows/ dir (resumable, disjoint symbols = no collision), then one
# assemble step. Each worker holds ~2.1-2.7GB RSS once the 2M-contract
# universe is loaded (the earlier ~1.2GB profile missed that phase; 4 shards
# OOM-churned the 7.7GB WSL cap on 2026-07-16). Sizing: 2 shards under the
# default ~7.7GB WSL cap; 3 under the 12GB .wslconfig cap set 2026-07-17.
set -uo pipefail
cd /home/mrhea/HealysBacktester
export NN_META_POOL=v31

pkill -f 'nn_meta.build_meta_dataset' 2>/dev/null || true
sleep 2

N=${1:-3}
./venv/bin/python - "$N" <<'PY'
import json, sys
n = int(sys.argv[1])
spec = json.load(open('nn_meta/artifacts_v31/baseline_spec.json'))
syms = sorted(spec['symbols'])
for k in range(n):
    open(f'/tmp/bshard_{k}.txt', 'w').write(','.join(syms[k::n]))   # round-robin
print(f'sharded {len(syms)} frozen symbols into {n}')
PY

run_shard(){
  local k=$1 syms
  syms=$(cat /tmp/bshard_$k.txt)
  until ./venv/bin/python -m nn_meta.build_meta_dataset --symbols "$syms" \
      >> v31_build_$k.log 2>&1; do
    echo "== build shard $k exited nonzero — resuming in 15s ==" >> v31_build_$k.log
    sleep 15
  done
  echo "== build shard $k COMPLETE ==" >> v31_build_$k.log
}

pids=()
for k in $(seq 0 $((N-1))); do
  run_shard "$k" & pids+=($!)
  echo "launched build shard $k (pid $!)"
  sleep 5
done
for p in "${pids[@]}"; do wait "$p"; done

echo "=== all shards done — assembling dataset ==="
./venv/bin/python -m nn_meta.build_meta_dataset --assemble
echo "PARALLEL-BUILD-DONE"
