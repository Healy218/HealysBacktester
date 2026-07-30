#!/usr/bin/env bash
# Parallel v3.1 dataset build: N symbol shards writing per-symbol rows to a
# shared meta_rows/ dir (resumable, disjoint symbols = no collision), then one
# assemble step. Each worker holds ~2.1-2.7GB RSS once the 2M-contract
# universe is loaded (the earlier ~1.2GB profile missed that phase; 4 shards
# OOM-churned the 7.7GB WSL cap on 2026-07-16).
#
# Sizing used to be a hardcoded 3, which was the most that fit the retired
# WSL2 box's 12GB .wslconfig cap. Native Pop!_OS has ~15.5GB and 12 threads,
# so that constant now leaves a shard's worth of headroom unused. Auto-size
# from what is ACTUALLY free instead of a new constant: a closed desktop earns
# an extra shard, and this needs no retuning if the 3.6GHz turbo cap (see the
# crash investigation) comes off. Pass N explicitly to override.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export NN_META_POOL=v31

pkill -f 'nn_meta.build_meta_dataset' 2>/dev/null || true
sleep 2

# 2800MB/shard = the documented 2.1-2.7GB worst-observed RSS, rounded up.
. "$(dirname "$(readlink -f "$0")")/lib/autosize.sh"
N=${1:-$(autosize_workers 2800)}
autosize_report "build" "$N"
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
