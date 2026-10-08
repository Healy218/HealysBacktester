# scripts/build_v8_stage1_signals.py — V8.1: long signals for every variant.
"""Compute every stage-1 variant's long entry/exit signals for every pool
symbol on 1h and 1d bars (adjusted OHLCV, truncated at 2025-12-31 so the
holdout is never read), mapped onto a common time grid and bit-packed.

Output under --out/<tf>/: grid.json (bar keys), variants.json, and one
<ticker>.npz per symbol with E, X packed along time (np.packbits, axis=1),
shape (variants, ceil(T/8)). Resumable per symbol; process pool sized by
nn_meta.v8_parallel.autosize_workers. Verifies the stage-0 contract first.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract  # noqa: E402
from nn_meta import v8_signals as vs  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
DEFAULT_OUT = REPO / "nn_meta" / "validation" / "v8-stage1-20261008-r0" / "signals"
END = "2025-12-31"
_RENAME = {"adj_open": "Open", "adj_high": "High", "adj_low": "Low",
           "adj_close": "Close", "adj_volume": "Volume"}


def load_bars(tf: str) -> pd.DataFrame:
    path = BARS / ("bars_1h.parquet" if tf == "1h" else "bars_1d.parquet")
    cols = ["ticker", "date", *_RENAME] + (["hour_bin"] if tf == "1h" else [])
    d = pd.read_parquet(path, columns=cols)
    d = d[d["date"] <= END]
    d["key"] = d["date"] + ("|" + d["hour_bin"].astype(int).astype(str) if tf == "1h" else "")
    return d.sort_values(["ticker", "key"], ignore_index=True)


def _work(job):
    ticker, tf, frame, grid_pos, out = job
    path = Path(out) / f"{ticker}.npz"
    if path.exists():
        return ticker, "done"
    variants = vs.variants_for(tf)
    bars = frame.rename(columns=_RENAME)[["Open", "High", "Low", "Close", "Volume"]].reset_index(drop=True)
    E, X = vs.symbol_signals(bars, variants)
    T = grid_pos["T"]
    Eg = np.zeros((len(variants), T), bool)
    Xg = np.zeros((len(variants), T), bool)
    pos = np.asarray(grid_pos["pos"])
    Eg[:, pos], Xg[:, pos] = E, X
    tmp = path.with_suffix(".tmp.npz")
    np.savez(tmp, E=np.packbits(Eg, axis=1), X=np.packbits(Xg, axis=1), T=T)
    tmp.replace(path)
    return ticker, f"{int(E.sum())} entries"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--tf", choices=vs.TIMEFRAMES, nargs="*", default=list(vs.TIMEFRAMES))
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    v8_contract.verify()
    workers, why = autosize_workers(per_worker_mb=1500, cap=args.workers)
    for tf in args.tf:
        out = args.out / tf
        out.mkdir(parents=True, exist_ok=True)
        d = load_bars(tf)
        grid = sorted(d["key"].unique())
        index = {k: i for i, k in enumerate(grid)}
        (out / "grid.json").write_text(json.dumps(grid) + "\n")
        (out / "variants.json").write_text(json.dumps(vs.variants_for(tf)) + "\n")
        jobs = []
        for t, g in d.groupby("ticker", sort=True):
            if args.only and t not in args.only.split(","):
                continue
            jobs.append((t, tf, g.drop(columns=["ticker", "date", "key"] + (["hour_bin"] if tf == "1h" else [])),
                         {"T": len(grid), "pos": [index[k] for k in g["key"]]}, str(out)))
        print(f"{tf}: {len(jobs)} symbols, grid {len(grid)} bars, {why}", flush=True)
        with ProcessPoolExecutor(workers) as ex:
            for i, (t, msg) in enumerate(ex.map(_work, jobs)):
                if (i + 1) % 20 == 0 or i + 1 == len(jobs):
                    print(f"  {tf} {i + 1}/{len(jobs)} {t}: {msg}", flush=True)


if __name__ == "__main__":
    main()
