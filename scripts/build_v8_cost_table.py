# scripts/build_v8_cost_table.py — V8.0-fills: freeze the stock half-spread table.
"""Build docs/specs/V8_COSTS_20261008.json from the measured NBBO sample.

cells:       median(mean_spread_bps)/2 per (price bucket, snapshot, year); a
             cell with < MIN_CELL samples borrows the same price bucket and
             snapshot pooled over years.
name_factor: exp(shrunk mean log(sample spread / its cell spread)) per
             ticker, shrinkage n / (n + SHRINK_N).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_fills as vf  # noqa: E402

QUOTES = REPO / "nn_meta" / "validation" / "v8-spreads-stock-20261008-r0" / "quotes.parquet"
OUT = REPO / "docs" / "specs" / "V8_COSTS_20261008.json"
MIN_CELL = 30
SHRINK_N = 200


def main() -> None:
    q = pd.read_parquet(QUOTES)
    q = q[q["mean_spread_bps"].notna()].copy()
    mid = (q["bid"] + q["ask"]) / 2
    q["price_bucket"] = vf.price_bucket(mid)
    q["snap_i"] = q["snap"].map({f"{m // 60:02d}:{m % 60:02d}": i
                                 for i, m in enumerate(vf.SNAP_MINUTES)})
    q["year"] = q["date"].str[:4].astype(int)
    full = q.groupby(["price_bucket", "snap_i", "year"])["mean_spread_bps"].agg(["median", "size"])
    pooled = q.groupby(["price_bucket", "snap_i"])["mean_spread_bps"].median()
    cells, borrowed = [], 0
    years = sorted(q["year"].unique())
    for pb in range(len(vf.PRICE_EDGES) - 1):
        for si in range(len(vf.SNAP_MINUTES)):
            for y in years:
                if (pb, si, y) in full.index and full.loc[(pb, si, y), "size"] >= MIN_CELL:
                    v, n = full.loc[(pb, si, y), "median"], int(full.loc[(pb, si, y), "size"])
                else:
                    v, n = pooled.get((pb, si), np.nan), 0
                    borrowed += 1
                cells.append({"price_bucket": pb, "snap": si, "year": int(y),
                              "half_spread_bps": round(float(v) / 2, 4), "n": n})
    cell_of = {(c["price_bucket"], c["snap"], c["year"]): 2 * c["half_spread_bps"] for c in cells}
    q["cell"] = [cell_of[k] for k in zip(q["price_bucket"], q["snap_i"], q["year"])]
    q["lr"] = np.log(q["mean_spread_bps"].clip(lower=1e-3) / q["cell"])
    g = q.groupby("ticker")["lr"].agg(["mean", "size"])
    factor = np.exp(g["mean"] * g["size"] / (g["size"] + SHRINK_N))
    payload = {
        "schema": "v8-costs-v1",
        "frozen_at": "2026-10-08",
        "source": str(QUOTES.relative_to(REPO)),
        "source_sha256": hashlib.sha256(QUOTES.read_bytes()).hexdigest(),
        "price_edges_usd": [e if e != float("inf") else None for e in vf.PRICE_EDGES],
        "snap_minutes_et": vf.SNAP_MINUTES,
        "slippage_bps": vf.SLIPPAGE_BPS, "sell_reg_bps": vf.SELL_REG_BPS,
        "taf_per_share": vf.TAF_PER_SHARE, "taf_cap": vf.TAF_CAP,
        "option_fee_per_contract": vf.OPTION_FEE_PER_CONTRACT,
        "min_cell": MIN_CELL, "shrink_n": SHRINK_N, "borrowed_cells": borrowed,
        "cells": cells,
        "name_factor": {t: round(float(v), 4) for t, v in factor.sort_index().items()},
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {OUT}: {len(cells)} cells ({borrowed} borrowed), "
          f"{len(factor)} name factors, range {factor.min():.2f}–{factor.max():.2f}")


if __name__ == "__main__":
    main()
