#!/usr/bin/env python
"""Parallel pre-warm of walk-forward checkpoints (freeze + dataset rows).

Produces EXACTLY the artifacts nn_meta.walkforward_meta.run_fold would create
sequentially (same functions, same file formats, same fold bounds), so the
canonical wf run resumes straight past its two expensive stages. Workers shard
by symbol and never share a state file; the merge-* commands combine shard
states into the canonical filenames the wf reads.

Deliberately does NOT import nn_meta.walkforward_meta: that would pull
tensorflow into every worker (~+0.5-1GB RSS each). That mattered under the
retired 12GB WSL cap and still does -- the shard count is now auto-sized from
free memory (scripts/lib/autosize.sh), so a fatter worker directly costs
shards. fold_boundaries is mirrored below instead -- keep in sync.

Order per fold:  freeze shards -> merge-freeze -> rows shards -> merge-rows.
Requires NN_META_POOL exported before launch (the launcher does it).
"""
import argparse
import json
import os
import sys

# invoked as `python scripts/wf_prewarm.py`, so sys.path[0] is scripts/ —
# put the repo root first so `nn_meta` imports like the -m entry points do
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import pandas as pd

from nn_meta import config
from nn_meta.baseline import freeze_symbol
from nn_meta.build_meta_dataset import build_symbol_rows
from nn_meta.providers import get_provider
from nn_meta.wf_context import experiment_key
from nn_meta.feature_contract import CONTRACT_VERSION

WF_DIR = config.ARTIFACTS / "wf"
MIN_TRAIN_PCT = 0.5     # MUST mirror nn_meta/walkforward_meta.py


def _save_json(path, obj):
    def _default(o):
        return o.item() if hasattr(o, "item") else float(o)
    path.write_text(json.dumps(obj, default=_default))


def _trading_days():
    # mirrors walkforward_meta._trading_days -- keep in sync
    panel = pd.read_parquet(config.UNDERLYING_15M_PARQUET,
                            columns=["symbol", "timestamp"])
    days = pd.DatetimeIndex(panel["timestamp"]).normalize().unique().sort_values()
    return days[(days >= config.WINDOW_START) & (days <= config.WINDOW_END)]


def fold_boundaries(n_folds):
    # mirrors walkforward_meta.fold_boundaries -- keep in sync
    days = _trading_days()
    n = len(days)
    oos_size = int(n * (1 - MIN_TRAIN_PCT) / n_folds)
    out = []
    for k in range(n_folds):
        i_end = int(n * MIN_TRAIN_PCT) + k * oos_size
        j_end = min(i_end + oos_size, n) - 1
        if j_end <= i_end:
            break
        out.append((days[i_end - 1].date().isoformat(),
                    days[i_end].date().isoformat(),
                    days[j_end].date().isoformat()))
    return out


def _bounds(fold, folds):
    return fold_boundaries(folds)[fold - 1]


def cmd_freeze(a):
    train_end, _, _ = _bounds(a.fold, a.folds)
    syms = config.UNDERLYINGS[a.shard::a.of]
    sf = WF_DIR / f"fold{a.fold}_spec_shard{a.shard}.json"
    state = json.loads(sf.read_text()) if sf.exists() else {"attempted": [], "symbols": {}}
    provider = get_provider()
    for sym in syms:
        if sym in state["attempted"]:
            continue
        try:
            entry = freeze_symbol(sym, provider, train_start=config.WINDOW_START,
                                  train_end=train_end)
        except Exception as e:
            print(f"freeze {sym} FAILED: {e}", flush=True)
            entry = None
        if entry is not None:
            state["symbols"][sym] = entry
        state["attempted"].append(sym)
        _save_json(sf, state)
        print(f"froze {sym} ({len(state['attempted'])}/{len(syms)})", flush=True)


def cmd_merge_freeze(a):
    merged = {"attempted": [], "symbols": {}}
    for k in range(a.of):
        sf = WF_DIR / f"fold{a.fold}_spec_shard{k}.json"
        st = json.loads(sf.read_text())
        want = config.UNDERLYINGS[k::a.of]
        missing = [s for s in want if s not in st["attempted"]]
        if missing:
            raise SystemExit(f"freeze shard {k} incomplete, missing: {missing[:5]}")
        merged["attempted"] += st["attempted"]
        merged["symbols"].update(st["symbols"])
    _save_json(WF_DIR / f"fold{a.fold}_spec.json", merged)
    print(f"merged spec: {len(merged['symbols'])} frozen / "
          f"{len(merged['attempted'])} attempted", flush=True)


def cmd_rows(a):
    _, _, oos_end = _bounds(a.fold, a.folds)
    spec = json.loads((WF_DIR / f"fold{a.fold}_spec.json").read_text())
    rows_dir = WF_DIR / f"fold{a.fold}_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    df_file = rows_dir / f"done_shard{a.shard}.json"
    done = set(json.loads(df_file.read_text())) if df_file.exists() else set()
    syms = [s for s in config.UNDERLYINGS[a.shard::a.of] if s in spec["symbols"]]
    provider = get_provider()
    for sym in syms:
        if sym in done:
            continue
        df = build_symbol_rows(sym, spec["symbols"][sym], provider,
                               window_start=config.WINDOW_START, window_end=oos_end)
        if not df.empty:
            tmp = rows_dir / f"{sym}.parquet.tmp"
            df.to_parquet(tmp, index=False)
            os.replace(tmp, rows_dir / f"{sym}.parquet")
        done.add(sym)
        _save_json(df_file, sorted(done))
        print(f"rows {sym} ({len(done)}/{len(syms)})", flush=True)


def cmd_merge_rows(a):
    rows_dir = WF_DIR / f"fold{a.fold}_rows"
    spec = json.loads((WF_DIR / f"fold{a.fold}_spec.json").read_text())
    done = set()
    for k in range(a.of):
        f = rows_dir / f"done_shard{k}.json"
        if f.exists():
            done |= set(json.loads(f.read_text()))
    missing = [s for s in spec["symbols"] if s not in done]
    if missing:
        raise SystemExit(f"rows incomplete, missing: {missing[:5]}")
    _save_json(rows_dir / "done.json", sorted(done))
    print(f"merged rows: {len(done)} symbols done", flush=True)


def main():
    global WF_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["freeze", "merge-freeze", "rows", "merge-rows"])
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--membership", action=argparse.BooleanOptionalAction, default=(config.POOL in ("v5", "v6")))
    ap.add_argument("--winner", type=str, default=str(config.MODEL_FINAL_DIR / "ensemble_config.json"))
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=3)
    a = ap.parse_args()
    from pathlib import Path
    winning = json.loads(Path(a.winner).read_text())
    if winning.get("feature_contract_version") != CONTRACT_VERSION:
        raise SystemExit("prewarm winner predates causal fixes; rerun training/selection")
    WF_DIR = config.ARTIFACTS / "wf" / experiment_key(winning, a.folds, a.membership)
    WF_DIR.mkdir(parents=True, exist_ok=True)
    {"freeze": cmd_freeze, "merge-freeze": cmd_merge_freeze,
     "rows": cmd_rows, "merge-rows": cmd_merge_rows}[a.cmd](a)


if __name__ == "__main__":
    main()
