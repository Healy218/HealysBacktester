# nn_meta/v8_fills.py — V8.0-fills: stock and option fill/cost model.
"""Vectorized fill prices for V8 backtests. Midpoint-only results never count.

Stock (stages 1–2):
    half_spread_bps = cell(price bucket, time slot, year) x name factor
      cell        median measured quoted spread / 2 from the Alpaca NBBO sample
                  (nn_meta/validation/v8-spreads-stock-20261008-r0), frozen in
                  docs/specs/V8_COSTS_20261008.json
      time slot   the sample's 13 snapshots (09:45 … 15:45 ET); a fill time maps
                  to the nearest snapshot (before 09:45 → 09:45)
      name factor per-name median spread ratio to its cells, shrunk toward 1
    buy  = ref x (1 + m x (half_spread_bps + SLIPPAGE_BPS) / 1e4)
    sell = ref x (1 - m x (half_spread_bps + SLIPPAGE_BPS) / 1e4)
    m = cost multiplier (1.0 primary, 1.5 stress); ref = bar price (proxy mid)
    fees: Robinhood $0 commission; on sells a conservative 0.3 bp of value
    (≥ the highest SEC Section 31 rate in 2021–2026, $27.80/M) plus FINRA TAF
    $0.000166/share capped at $8.30.

Options (stage 3):
    buy = mid + k x half_spread, sell = mid - k x half_spread (k = 1.0 primary,
    0.5 sensitivity), plus a conservative $0.05 per contract per side for
    exchange/regulatory pass-through fees.

Cost-table caveat: cells and name factors use the whole 2021–2026 sample
(within-year cells), so a backtest's costs see later quotes. Costs are not
signals; the 1.5x stress bounds the effect.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
COST_TABLE = REPO / "docs" / "specs" / "V8_COSTS_20261008.json"

SLIPPAGE_BPS = 1.0
SELL_REG_BPS = 0.3
TAF_PER_SHARE = 0.000166
TAF_CAP = 8.30
OPTION_FEE_PER_CONTRACT = 0.05
PRICE_EDGES = [0, 5, 10, 20, 50, 100, float("inf")]
SNAP_MINUTES = [9 * 60 + 45 + 30 * k for k in range(13)]  # 09:45 … 15:45 ET


@lru_cache(maxsize=1)
def load_table(path: str = str(COST_TABLE)) -> dict:
    t = json.loads(Path(path).read_text())
    cells = {(c["price_bucket"], c["snap"], c["year"]): c["half_spread_bps"]
             for c in t["cells"]}
    return {"cells": cells, "name_factor": t["name_factor"],
            "years": sorted({c["year"] for c in t["cells"]})}


def price_bucket(price) -> np.ndarray:
    return np.searchsorted(PRICE_EDGES, np.asarray(price, float), side="right") - 1


def snap_index(minute_of_day) -> np.ndarray:
    m = np.asarray(minute_of_day, float)
    idx = np.rint((m - SNAP_MINUTES[0]) / 30.0)
    return np.clip(idx, 0, len(SNAP_MINUTES) - 1).astype(int)


def stock_half_spread_bps(ticker, price, minute_of_day, year, table=None) -> np.ndarray:
    tb = table or load_table()
    ticker = np.asarray(ticker, object)
    pb = price_bucket(price)
    sn = snap_index(minute_of_day)
    yr = np.clip(np.asarray(year, int), tb["years"][0], tb["years"][-1])
    cell = np.array([tb["cells"][(int(p), int(s), int(y))]
                     for p, s, y in zip(pb, sn, yr)], float)
    factor = np.array([tb["name_factor"].get(t, 1.0) for t in ticker], float)
    return cell * factor


def stock_fill(side, ref_price, shares, ticker, minute_of_day, year,
               cost_mult: float = 1.0, table=None) -> pd.DataFrame:
    """side: +1 buy, -1 sell (arrays broadcast). Returns fill price, cash
    flow (negative for buys, net of fees for sells) and the fee."""
    side = np.asarray(side, int)
    ref = np.asarray(ref_price, float)
    shares = np.asarray(shares, float)
    hs = stock_half_spread_bps(ticker, ref, minute_of_day, year, table)
    px = ref * (1 + side * cost_mult * (hs + SLIPPAGE_BPS) / 1e4)
    value = px * shares
    sell = side < 0
    fee = np.where(sell, value * SELL_REG_BPS / 1e4
                   + np.minimum(shares * TAF_PER_SHARE, TAF_CAP), 0.0)
    cash = np.where(sell, value - fee, -value)
    return pd.DataFrame({"fill_price": px, "half_spread_bps": hs,
                         "fee": fee, "cash": cash})


def option_fill(side, mid, half_spread, contracts, k: float = 1.0) -> pd.DataFrame:
    """Per-share option premium fill and cash for `contracts` (x100)."""
    side = np.asarray(side, int)
    mid = np.asarray(mid, float)
    px = mid + side * k * np.asarray(half_spread, float)
    contracts = np.asarray(contracts, float)
    fee = contracts * OPTION_FEE_PER_CONTRACT
    cash = -side * px * 100 * contracts - fee
    return pd.DataFrame({"fill_price": px, "fee": fee, "cash": cash})
