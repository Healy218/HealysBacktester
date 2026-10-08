# scripts/build_v8_vol_panel.py — V8.2-iv/-forecast: daily vol panel.
"""Per (ticker, date) through 2025-12-31: spot, IV30 (ATM, constant 30-day),
HAR 21-day forecast vol, and realized forward 21-day vol (evaluation only).

IV per month runs in a process pool (nn_meta.v8_vol.atm_iv_by_expiry / iv30);
HAR runs per ticker. Output: <stage2>/vol_panel.parquet and vol_summary.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract, v8_vol  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

STAGE2 = REPO / "nn_meta" / "validation" / "v8-stage2-20261008-r0"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
END = "2025-12-31"


def _iv_month(path: str) -> pd.DataFrame:
    ch = pd.read_parquet(path, columns=["date", "ticker", "expiry", "cp", "strike", "close", "volume"])
    ch = ch[ch["date"] <= END]
    if ch.empty:
        return pd.DataFrame()
    spot = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "close"])
    spot = spot[spot["date"].isin(ch["date"].unique())].rename(columns={"close": "S"})
    return v8_vol.iv30(v8_vol.atm_iv_by_expiry(ch, spot))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    v8_contract.verify()
    months = sorted(str(p) for p in (STAGE2 / "chains").glob("*.parquet")
                    if p.stem <= END[:7])
    workers, why = autosize_workers(per_worker_mb=3000, cap=args.workers)
    print(f"IV: {len(months)} months, {why}", flush=True)
    with ProcessPoolExecutor(workers) as ex:
        iv = pd.concat(list(ex.map(_iv_month, months)), ignore_index=True)
    h = pd.read_parquet(BARS / "bars_1h.parquet",
                        columns=["ticker", "date", "hour_bin", "adj_open", "adj_close"])
    h = h[h["date"] <= END]
    rv = v8_vol.realized_variance(h)
    har = v8_vol.har_direct(rv)
    panel = rv.merge(har, on=["ticker", "date"], how="left").merge(iv, on=["ticker", "date"], how="left")
    panel.to_parquet(STAGE2 / "vol_panel.parquet", index=False)
    have = panel.dropna(subset=["iv30"])
    summary = {
        "rows": int(len(panel)), "with_iv30": int(len(have)),
        "tickers_with_iv30": int(have["ticker"].nunique()),
        "iv30_method": have["iv30_method"].value_counts().to_dict(),
        "median_iv30_by_ticker": have.groupby("ticker")["iv30"].median().round(3).to_dict(),
        "median_iv_over_realized_fwd": float((have["iv30"] / have["rv_fwd_vol"]).median()),
        "median_har_over_realized_fwd": float((panel["har_vol"] / panel["rv_fwd_vol"]).median()),
    }
    (STAGE2 / "vol_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "median_iv30_by_ticker"}, indent=1))


if __name__ == "__main__":
    main()
