# nn_meta/vol_features.py — vol-regime track stage 1 (docs/specs/VOL_SPEC.md).
"""Per-session realized-volatility features from the 9-year 1m underlying
crawl, point-in-time by construction: every row's ``available_at`` is that
session's close, and nothing in the row reads a later bar.

The crawl's bars are UTC-stamped and include extended hours; RTH filtering
converts to America/New_York (DST-aware) and keeps 09:30–16:00. Sessions
with thin coverage are FLAGGED (``low_coverage``), never silently dropped or
imputed — consumers decide.

Run:  ./venv/bin/python -m nn_meta.vol_features --symbols SPY,QQQ
      [--data v3/data/underlying] [--out nn_meta/artifacts_vol]
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

RTH_START, RTH_END = "09:30", "16:00"
FULL_SESSION_BARS = 390
LOW_COVERAGE_BARS = 300


def rth_bars(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """UTC 1m bars → RTH-only, indexed in America/New_York (naive)."""
    idx = pd.to_datetime(bars_1m.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    local = bars_1m.copy()
    local.index = idx.tz_convert("America/New_York").tz_localize(None)
    local = local[local.index.dayofweek < 5]
    return local.between_time(RTH_START, RTH_END, inclusive="left")


def session_rv(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """One row per session: the VOL_SPEC stage-1 feature set."""
    rth = rth_bars(bars_1m)
    if rth.empty:
        return pd.DataFrame()
    out = []
    prev_close: float | None = None
    for day, g in rth.groupby(rth.index.normalize()):
        c = g["Close"].astype(float)
        r = np.log(c).diff().dropna().to_numpy()
        c5 = c.iloc[::5]
        r5 = np.log(c5).diff().dropna().to_numpy()
        close = float(c.iloc[-1])
        opn = float(g["Open"].astype(float).iloc[0])
        bpv = (np.pi / 2) * float(np.sum(np.abs(r[1:]) * np.abs(r[:-1])))
        rv = float(np.sum(r ** 2))
        row = {
            "date": day,
            "rv_1m": rv,
            "rv_5m": float(np.sum(r5 ** 2)),
            "bpv": bpv,
            "jump": max(rv - bpv, 0.0),
            "overnight_r2": (float(np.log(opn / prev_close) ** 2)
                             if prev_close and prev_close > 0 else np.nan),
            "ret_cc": (float(np.log(close / prev_close))
                       if prev_close and prev_close > 0 else np.nan),
            "close": close,
            "n_bars": int(len(g)),
            "low_coverage": bool(len(g) < LOW_COVERAGE_BARS),
            # known at the session close (NY) — stamped back to UTC
            "available_at": (pd.Timestamp(g.index[-1]) + pd.Timedelta(minutes=1)).tz_localize(
                "America/New_York").tz_convert("UTC").tz_localize(None),
        }
        out.append(row)
        prev_close = close
    return pd.DataFrame(out)


def build_symbol(symbol: str, data_dir: Path) -> pd.DataFrame:
    """All year-parquets of one symbol → the per-session feature frame."""
    files = sorted(f for f in glob.glob(str(data_dir / symbol / "*.parquet"))
                   if not f.endswith(".bak"))
    if not files:
        return pd.DataFrame()
    bars = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    return session_rv(bars)


def evaluate_symbol(daily: pd.DataFrame, *, n_folds: int = 3) -> list[dict]:
    """Baselines OOS on the INTRADAY rv target, overall and per regime
    tercile (trailing-21d mean RV, shifted one day so the regime label at t
    is known before t). The seat gate reads these rows."""
    from nn_meta.vol_forecast import GARCH11, HARRV, qlike
    from nn_meta.temporal_validation import expanding_folds

    ok = daily[~daily["low_coverage"]].dropna(subset=["ret_cc"]).reset_index(drop=True)
    if len(ok) < 120:
        return []
    dates = pd.DatetimeIndex(ok["date"])
    rv = ok["rv_1m"].to_numpy()
    rets = ok["ret_cc"].to_numpy()
    trail = pd.Series(rv).rolling(21).mean().shift(1)

    results: list[dict] = []
    for w in expanding_folds(pd.Series(dates), n_folds=n_folds):
        train = dates < w.test_start
        test_idx = np.where((dates >= w.test_start) & (dates <= w.test_end))[0]
        test_idx = test_idx[test_idx >= 22]
        if train.sum() < 60 or len(test_idx) == 0:
            continue
        # Regime boundaries, like the forecasting models, only see fold train.
        cuts = trail.loc[train].dropna().quantile([1 / 3, 2 / 3]).to_numpy()
        tercile = pd.Series(np.where(trail <= cuts[0], "calm",
                                     np.where(trail <= cuts[1], "mid", "stressed")))
        tercile.loc[trail.isna()] = None
        har = HARRV.fit(rv[train])
        garch = GARCH11.fit(rets[train])
        naive = float(rv[train].mean())
        har_f = np.clip(np.array([har.forecast_at(rv, t) for t in test_idx]),
                        1e-12, None)
        garch_f = np.array([garch.forecast_at(rets, t) for t in test_idx])
        realized = rv[test_idx]
        row = {"test_start": str(w.test_start.date()),
               "test_end": str(w.test_end.date()), "n_test": int(len(test_idx)),
               "har_qlike": qlike(realized, har_f),
               "garch_qlike": qlike(realized, garch_f),
               "naive_qlike": qlike(realized, np.full_like(realized, naive))}
        for regime in ("calm", "mid", "stressed"):
            m = (tercile.iloc[test_idx] == regime).to_numpy()
            if m.sum() >= 5:
                row[f"har_qlike_{regime}"] = qlike(realized[m], har_f[m])
                row[f"garch_qlike_{regime}"] = qlike(realized[m], garch_f[m])
        results.append(row)
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="comma list (default: all)")
    ap.add_argument("--data", type=Path, default=Path("v3/data/underlying"))
    ap.add_argument("--out", type=Path, default=Path("nn_meta/artifacts_vol"))
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()
    symbols = ([s.strip().upper() for s in args.symbols.split(",")] if args.symbols
               else sorted(p.name for p in args.data.iterdir() if p.is_dir()))
    (args.out / "features").mkdir(parents=True, exist_ok=True)
    evals = []
    for k, sym in enumerate(symbols, 1):
        fpath = args.out / "features" / f"{sym}.parquet"
        if args.skip_existing and fpath.exists():
            continue
        daily = build_symbol(sym, args.data)
        if daily.empty:
            print(f"  {sym}: no data", flush=True)
            continue
        tmp = fpath.with_suffix(".parquet.tmp")
        daily.to_parquet(tmp, index=False)
        tmp.replace(fpath)
        for row in evaluate_symbol(daily):
            evals.append({"symbol": sym, **row})
        print(f"[vol] {k}/{len(symbols)} {sym}: {len(daily)} sessions", flush=True)
    if evals:
        ev = pd.DataFrame(evals)
        tmp = args.out / "baseline_eval.parquet.tmp"
        ev.to_parquet(tmp, index=False)
        tmp.replace(args.out / "baseline_eval.parquet")
        agg = ev[["har_qlike", "garch_qlike", "naive_qlike"]].mean().round(4)
        print(f"mean QLIKE — {agg.to_dict()}")


if __name__ == "__main__":
    main()
