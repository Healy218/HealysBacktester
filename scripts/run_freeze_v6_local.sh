#!/usr/bin/env bash
# Home-box v6 ADDITIVE freeze (2026-09-05): sweep only the two new families
# (keltner, bbw_squeeze) for every v5 symbol, inheriting the other ten from
# v5's frozen spec; weekly-expiry names re-freeze in full on the extended
# DTE grid (nn_meta/weekly_expiry.py). CRWV timing: ~35 s per new family, so
# 441 symbols ≈ 4-5 h single-process — WORKERS shards run in parallel and
# each writes its own spec shard; merge with:
#   NN_META_POOL=v6 ./venv/bin/python -m nn_meta.freeze_baseline \
#       --merge "$(ls nn_meta/artifacts_v6/spec_shard_*.json | paste -sd,)"
# Resume-safe: freeze_all skips symbols already in its shard file.
# Run DETACHED (harness background tasks get killed on this box):
#   setsid nohup scripts/run_freeze_v6_local.sh > logs/freeze_v6_local.log 2>&1 &
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
export NN_META_POOL=v6
. scripts/lib/autosize.sh
WORKERS=${WORKERS:-$(autosize_workers 5000)}
BASE=nn_meta/artifacts_v5/baseline_spec.json
OUT=nn_meta/artifacts_v6
mkdir -p "$OUT" logs
echo "workers: $WORKERS | base spec: $BASE | started $(date -u +%FT%TZ)"

./venv/bin/python - "$WORKERS" <<'PY'
import json, sys
n = int(sys.argv[1])
syms = sorted(json.load(open("nn_meta/artifacts_v5/baseline_spec.json"))["symbols"])
for i in range(n):
    open(f"nn_meta/artifacts_v6/shard_{i}.txt", "w").write(",".join(syms[i::n]))
print(f"{len(syms)} symbols → {n} shards")
PY

pids=()
for i in $(seq 0 $((WORKERS-1))); do
  ./venv/bin/python -m nn_meta.freeze_baseline \
      --symbols "$(cat $OUT/shard_$i.txt)" \
      --strategies keltner,bbw_squeeze --base-spec "$BASE" \
      --out "$OUT/spec_shard_$i.json" > "logs/freeze_v6_shard_$i.log" 2>&1 &
  pids+=($!)
done
rc=0
for pid in "${pids[@]}"; do
  wait "$pid" || rc=1
done
[ "$rc" -eq 0 ] || { echo "LOCAL-FREEZE-FAILED" >&2; exit "$rc"; }
echo "LOCAL-FREEZE-DONE $(date -u +%FT%TZ)"
