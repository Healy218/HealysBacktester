# scripts/build_v9_ove_flow.py — V9 OVE-1: daily options-flow and dark-pool table (coverage only).
"""Per (ticker, trading day), from the V8 OPRA daily chains (2021-01 → 2026-09-14),
the raw stock close and FINRA consolidated short volume:

  call_vol, put_vol, call_trades, put_trades     contracts and prints
  call_prem, put_prem                            sum volume x close x 100 ($)
  st_otm_call_prem, st_otm_put_prem              DTE <= 14, strike 0-15% OTM
  block_call_vol, block_put_vol                  contracts whose day's average
                                                 print is >= BLOCK contracts
  st_otm_call_prem_at_high / _put_                the short-dated OTM premium in
                                                 contracts closing in the top 20%
                                                 of their day's range (buyer pressure)
  S, stock_volume                                raw close and volume (V8 bars)
  finra_short_ratio, finra_volume                FINRA short / total (2021-2025)
  days_since_earnings, days_to_earnings          trading days to/from the nearest
                                                 8-K Item 2.02 reaction day (the
                                                 next date is assumed known ahead)

Prices are last-trade closes, so premium dollars are approximate. No outcome
is computed here. Output (<out>/): flow.parquet, report.json. Process pool over
months.
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

from nn_meta import v9_oee  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

V = REPO / "nn_meta" / "validation"
CHAINS = V / "v8-stage2-20261008-r0" / "chains"
BARS = V / "v8-data-20261008-r0" / "bars_1d.parquet"
FINRA = V / "v8-events-20261008-r0" / "finra" / "short_volume.parquet"
FILINGS = V / "v8-events-20261008-r0" / "sec" / "filings.parquet"
DEFAULT_OUT = V / "v9-ove1-20261008-r0"
BLOCK = 20
ST_DTE = 14
OTM_MAX = 0.15


def _month(job):
    path, spot = job
    c = pd.read_parquet(path, columns=["date", "ticker", "expiry", "cp", "strike", "high", "low",
                                       "close", "volume", "transactions"])
    c = c[(c["volume"] > 0) & (c["close"] > 0)].merge(spot, on=["date", "ticker"])
    c["dte"] = (pd.to_datetime(c["expiry"]) - pd.to_datetime(c["date"])).dt.days
    c["prem"] = c["volume"] * c["close"] * 100
    call = c["cp"] == "C"
    m = c["strike"] / c["S"] - 1
    otm = np.where(call, (m > 0) & (m <= OTM_MAX), (m < 0) & (m >= -OTM_MAX))
    st_otm = otm & (c["dte"] >= 0) & (c["dte"] <= ST_DTE)
    block = c["volume"] / c["transactions"].clip(lower=1) >= BLOCK
    rng = c["high"] - c["low"]
    at_high = (rng > 0) & (c["close"] >= c["high"] - 0.2 * rng)
    cols = {
        "call_vol": c["volume"].where(call, 0), "put_vol": c["volume"].where(~call, 0),
        "call_trades": c["transactions"].where(call, 0), "put_trades": c["transactions"].where(~call, 0),
        "call_prem": c["prem"].where(call, 0), "put_prem": c["prem"].where(~call, 0),
        "st_otm_call_prem": c["prem"].where(call & st_otm, 0),
        "st_otm_put_prem": c["prem"].where(~call & st_otm, 0),
        "block_call_vol": c["volume"].where(call & block, 0),
        "block_put_vol": c["volume"].where(~call & block, 0),
        "st_otm_call_prem_at_high": c["prem"].where(call & st_otm & at_high, 0),
        "st_otm_put_prem_at_high": c["prem"].where(~call & st_otm & at_high, 0),
    }
    d = pd.DataFrame(cols).assign(date=c["date"].to_numpy(), ticker=c["ticker"].to_numpy())
    g = d.groupby(["ticker", "date"]).sum().reset_index()
    g["n_contracts"] = c.groupby(["ticker", "date"]).size().to_numpy()
    return path.stem, g


def earnings_distance(flow: pd.DataFrame, days: list[str]) -> pd.DataFrame:
    fl = pd.read_parquet(FILINGS)
    e = fl[(fl["form"] == "8-K") & fl["items"].fillna("").str.contains("2.02", regex=False)]
    _, r = v9_oee.event_days(pd.to_datetime(e["acceptance_utc"], utc=True), days)
    react = pd.DataFrame({"ticker": e["ticker"].to_numpy(), "r": r})
    react = react[react["r"] >= 0]
    pos = {d: i for i, d in enumerate(days)}
    flow["i"] = flow["date"].map(pos)
    since = np.full(len(flow), np.nan)
    to = np.full(len(flow), np.nan)
    for t, idx in flow.groupby("ticker").indices.items():
        rs = np.sort(react.loc[react["ticker"] == t, "r"].unique())
        if not len(rs):
            continue
        ii = flow["i"].to_numpy()[idx]
        k = np.searchsorted(rs, ii, side="right")          # reactions <= day
        prev = np.where(k > 0, rs[np.maximum(k - 1, 0)], -1)
        since[idx] = np.where(k > 0, ii - prev, np.nan)
        k2 = np.searchsorted(rs, ii, side="right")          # next reaction strictly after
        nxt = np.where(k2 < len(rs), rs[np.minimum(k2, len(rs) - 1)], -1)
        to[idx] = np.where(k2 < len(rs), nxt - ii, np.nan)
    flow["days_since_earnings"], flow["days_to_earnings"] = since, to
    return flow.drop(columns="i")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    bars = pd.read_parquet(BARS, columns=["ticker", "date", "close", "volume"])
    days = sorted(bars["date"].unique())
    spot = bars.rename(columns={"close": "S", "volume": "stock_volume"})
    files = sorted(CHAINS.glob("*.parquet"))
    jobs = [(p, spot[spot["date"].str[:7] == p.stem][["ticker", "date", "S"]]) for p in files]
    workers, why = autosize_workers(per_worker_mb=2500, cap=args.workers)
    print(f"{len(files)} chain months; {why}", flush=True)
    parts = []
    with ProcessPoolExecutor(workers) as ex:
        for m, g in ex.map(_month, jobs):
            parts.append(g)
    flow = pd.concat(parts, ignore_index=True)
    flow = flow.merge(spot, on=["ticker", "date"], how="left")
    fn = pd.read_parquet(FINRA, columns=["ticker", "date", "short_volume", "total_volume"])
    fn = fn.groupby(["ticker", "date"], as_index=False).sum()
    fn["finra_short_ratio"] = fn["short_volume"] / fn["total_volume"].replace(0, np.nan)
    flow = flow.merge(fn.rename(columns={"total_volume": "finra_volume"})[
        ["ticker", "date", "finra_short_ratio", "finra_volume"]], on=["ticker", "date"], how="left")
    flow = earnings_distance(flow.sort_values(["ticker", "date"]).reset_index(drop=True), days)
    flow.to_parquet(args.out / "flow.parquet", index=False)
    rep = {
        "rows": len(flow), "tickers": int(flow["ticker"].nunique()),
        "dates": [flow["date"].min(), flow["date"].max()],
        "rows_by_year": flow.groupby(flow["date"].str[:4]).size().to_dict(),
        "with_spot": float(flow["S"].notna().mean()),
        "with_finra": float(flow["finra_short_ratio"].notna().mean()),
        "finra_dates": [fn["date"].min(), fn["date"].max()],
        "with_earnings_distance": float(flow["days_to_earnings"].notna().mean()),
        "median_daily": flow[["call_vol", "put_vol", "call_prem", "put_prem", "st_otm_call_prem",
                              "st_otm_put_prem", "block_call_vol", "n_contracts"]].median().to_dict(),
        "share_days_with_st_otm_call_flow": float((flow["st_otm_call_prem"] > 0).mean()),
        "share_days_with_block_calls": float((flow["block_call_vol"] > 0).mean()),
        "note": "coverage only; no forward returns computed",
    }
    (args.out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
