# scripts/build_v8_option_chains.py — V8.2-data: daily option chains.
"""Extract daily per-contract OPRA aggregates for the V8 pool (17 ETFs + all
pool tech names) from the sealed V7 day files on MRHA (read in place), with
the same root identity as the PIT universe (V8 aliases/rekeys from the PIT
report, TICKER_ALIASES, test roots dropped).

Output: <out>/chains/<yyyy-mm>.parquet with date, ticker (underlying, current
symbol), root, expiry, cp, strike, open, high, low, close, volume,
transactions. Process pool over months, resumable per month.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import importlib.util  # noqa: E402

from nn_meta import universe_pit as up  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "build_v8_universe_pit", REPO / "scripts" / "build_v8_universe_pit.py")
_pit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pit)

PIT_ROOT = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
DEFAULT_OUT = REPO / "nn_meta" / "validation" / "v8-stage2-20261008-r0"


def root_map() -> tuple[dict, list]:
    """{raw root: pool ticker} plus date-bounded rekeys [(root, before, new)]."""
    rep = json.loads((PIT_ROOT / "report.json").read_text())
    pool = json.loads(POOL.read_text())
    want = set().union(*(set(v["tech"]) for v in pool["months"].values()))
    want |= set(pool["rule"]["etfs_every_month"])
    aliases = rep["aliases"]

    def resolve(r):
        seen = set()
        while r in aliases and r not in seen:
            seen.add(r); r = aliases[r]
        return r
    roots = set(want) | set(aliases)
    out = {}
    for r in roots:
        t = up.root_to_ticker(resolve(r))
        if t in want:
            out[r] = t
    return out, [tuple(x) for x in rep["rekeys"]]


def _month(job):
    month, files, out, rmap, rekeys = job
    path = Path(out) / f"{month}.parquet"
    if path.exists():
        return month, "done"
    frames = []
    for day, obj in files:
        with gzip.open(obj, "rb") as f:
            raw = pd.read_csv(f, usecols=["ticker", "open", "high", "low", "close",
                                          "volume", "transactions"])
        tk = raw["ticker"].str[2:]                      # strip "O:"
        tail = tk.str[-15:]
        root = tk.str[:-15]
        keep = raw["ticker"].str.startswith("O:") & root.isin(rmap)
        if not keep.any():
            continue
        d = raw[keep].copy()
        d["root"] = root[keep].to_numpy()
        tl = tail[keep]
        d["expiry"] = ("20" + tl.str[0:2] + "-" + tl.str[2:4] + "-" + tl.str[4:6]).to_numpy()
        d["cp"] = tl.str[6].to_numpy()
        d["strike"] = tl.str[7:].astype(np.int64).to_numpy() / 1000
        d["date"] = day
        d["ticker"] = d["root"].map(rmap)
        for r, before, _ in rekeys:                      # e.g. pre-seam META ETF
            d = d[~((d["root"] == r) & (d["date"] < before))]
        frames.append(d[["date", "ticker", "root", "expiry", "cp", "strike", "open",
                         "high", "low", "close", "volume", "transactions"]])
    df = pd.concat(frames, ignore_index=True)
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    return month, f"{len(df)} rows"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    out = args.out / "chains"
    out.mkdir(parents=True, exist_ok=True)
    rmap, rekeys = root_map()
    days = _pit.sealed_day_files()
    months: dict[str, list] = {}
    for day, (_, obj) in sorted(days.items()):
        months.setdefault(day[:7], []).append((day, str(obj)))
    workers, why = autosize_workers(per_worker_mb=2500, cap=args.workers)
    print(f"{len(rmap)} roots → {len(set(rmap.values()))} tickers; {len(months)} months; {why}",
          flush=True)
    jobs = [(m, f, str(out), rmap, rekeys) for m, f in sorted(months.items())]
    with ProcessPoolExecutor(workers) as ex:
        for m, msg in ex.map(_month, jobs):
            print(f"  {m}: {msg}", flush=True)


if __name__ == "__main__":
    main()
