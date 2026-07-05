# nn_meta/build_meta_dataset.py
"""Meta-label dataset: one row per (proposed trade, target DTE).

For every symbol in the frozen baseline spec:
  1. Frozen-param MA signals over the whole window → proposed trades
     (same simulator + sim config as the dashboard; stops/trend filter shape
     the timeline).
  2. Each trade is executed as an option at every DTE in config.DTE_GRID
     through options/execution.py → realized net option return (the label).
  3. Features are computed strictly from information available at the SIGNAL
     bar's close (vectorbt fills stock signals at that close, so this is the
     decision information set): 15m technicals, daily option-surface features
     as-of the PREVIOUS day's close, and trade context.

Timeline note: the execution engine fills option entries at the first option
bar STRICTLY AFTER the signal bar (its open is at/after the signal close) —
honest fills, no lookahead. The legacy same-bar convention remains available
via EXEC_CONFIG["FILL_SAME_BAR"].

Unfilled proposals are kept with net_return = NaN (fill-failure analysis);
training drops them.

Run:  python -m nn_meta.build_meta_dataset [--symbols SPY,QQQ]
"""
from __future__ import annotations

import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import numpy as np
import pandas as pd

from utils.logging_utils import setup_logging
from options.execution import Execution, to_naive_utc
from options.data.hybrid_provider import HybridCachedProvider
from nn_meta import config
from nn_meta.baseline import (load_underlying_15m, load_spec, propose_trades,
                              execute_at_dte)

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-META-DS"

# Feature list (single source of truth — train / select / runner import this).
META_FEATURES = [
    # 15m technicals at the signal bar close
    "ma_gap", "px_vs_fast", "rsi14", "macd_hist", "bb_z",
    "ret_1", "ret_8", "ret_26", "session_gap", "tod", "dow",
    # daily option-surface state, as-of previous close
    "rvol_5", "rvol_21", "atm_iv_near", "atm_iv_far",
    "term_slope", "iv_chg_5", "pc_ratio",
    # trade context
    "dir_short", "dte_frac", "prem_spot", "moneyness", "bars_since_signal",
]


# ── 15m technical features ────────────────────────────────────────────────────

def technical_features(bars: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    """Per-bar features from the underlying's 15m series (full-history warmup)."""
    close = bars["Close"]
    ma_f = close.rolling(fast).mean()
    ma_s = close.rolling(slow).mean()

    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_hist = (macd - macd.ewm(span=9, adjust=False).mean()) / close

    ma20 = close.rolling(20).mean()
    sd20 = close.rolling(20).std()
    bb_z = (close - ma20) / (2 * sd20.replace(0, np.nan))

    day = bars.index.normalize()
    first_open = bars["Open"].groupby(day).transform("first")
    prev_last_close = close.groupby(day).last().shift(1)
    session_gap = first_open / day.map(prev_last_close) - 1

    bar_of_day = pd.Series(bars.groupby(day).cumcount().values, index=bars.index)

    return pd.DataFrame({
        "ma_gap": (ma_f - ma_s) / close,
        "px_vs_fast": close / ma_f - 1,
        "rsi14": rsi / 100.0,
        "macd_hist": macd_hist,
        "bb_z": bb_z,
        "ret_1": close.pct_change(),
        "ret_8": close.pct_change(8),
        "ret_26": close.pct_change(26),
        "session_gap": session_gap,
        "tod": bar_of_day / 26.0,
        "dow": pd.Series(bars.index.dayofweek, index=bars.index) / 4.0,
    })


# ── daily option-surface features (from the completed nn_options_signal panel) ─

_SURFACE_COLS = ["rvol_5", "rvol_21", "atm_iv_near", "atm_iv_far",
                 "term_slope", "iv_chg_5", "pc_ratio"]


def load_surface_features() -> pd.DataFrame:
    """Per-(underlying, date) surface state from dataset.parquet."""
    panel = pd.read_parquet(config.SURFACE_DATASET_PARQUET,
                            columns=["underlying", "date"] + _SURFACE_COLS)
    surf = panel.groupby(["underlying", "date"], as_index=False).first()
    return surf.sort_values("date")


def join_surface_asof(rows: pd.DataFrame, surface: pd.DataFrame) -> pd.DataFrame:
    """As-of join on the PREVIOUS available surface date (no same-day peek)."""
    rows = rows.sort_values("entry_date")
    out = []
    for sym, grp in rows.groupby("symbol"):
        s = surface[surface["underlying"] == sym]
        if s.empty:
            g = grp.copy()
            for c in _SURFACE_COLS:
                g[c] = np.nan
            out.append(g)
            continue
        merged = pd.merge_asof(
            grp, s.drop(columns=["underlying"]),
            left_on="entry_date", right_on="date",
            allow_exact_matches=False,     # strictly previous close
        )
        out.append(merged.drop(columns=["date"]))
    return pd.concat(out, ignore_index=True)


# ── per-symbol row construction ───────────────────────────────────────────────

def build_symbol_rows(symbol: str, spec_entry: dict, provider,
                      window_start: str = config.WINDOW_START,
                      window_end: str = config.WINDOW_END) -> pd.DataFrame:
    bars = load_underlying_15m(symbol)
    if bars.empty:
        logger.warning(f"[{_TAG}] {symbol}: no bars")
        return pd.DataFrame()

    fast, slow = spec_entry["fast"], spec_entry["slow"]
    trades = propose_trades(bars, fast, slow, window_start, window_end)
    if len(trades) > config.MAX_SIGNALS_PER_NAME:
        logger.warning(f"[{_TAG}] {symbol}: truncating {len(trades)} trades to cap")
        trades = trades[:config.MAX_SIGNALS_PER_NAME]
    if not trades:
        return pd.DataFrame()

    feats = technical_features(bars, fast, slow)
    close = bars["Close"]

    # signal-gap feature: bars since the previous proposed entry
    entry_ts = [to_naive_utc(t[0]) for t in trades]
    entry_pos = bars.index.searchsorted(entry_ts)
    gaps = np.diff(entry_pos, prepend=entry_pos[0])

    ex = Execution(symbol, config.INTERVAL, window_end, provider,
                   config.EXEC_CONFIG)
    all_rows = []
    for dte in config.DTE_GRID:
        records, meta = execute_at_dte(symbol, trades, bars, dte, provider,
                                       window_end, ex=ex)
        logger.info(f"[{_TAG}] {symbol} {dte}DTE: {meta['n_executed']}/"
                    f"{meta['n_signals']} executed, {meta['n_rolls']} rolls")
        for i, r in enumerate(records):
            ts = to_naive_utc(r["entry_ts"])
            spot = float(close.loc[:ts].iloc[-1]) if len(close.loc[:ts]) else np.nan
            f = feats.loc[:ts]
            frow = f.iloc[-1] if len(f) else pd.Series(index=feats.columns, dtype=float)
            prem = r["entry_premium"]
            strike = r["strike"]
            all_rows.append({
                "symbol": symbol, "trade_idx": r["trade_idx"], "dte": dte,
                "entry_ts": ts, "entry_date": ts.normalize(),
                "exit_ts": to_naive_utc(r["exit_ts"]),
                "direction": r["direction"], "right": r["right"],
                "contract": r["contract"], "strike": strike,
                "expiration": r["expiration"],
                "entry_premium": prem, "fill_lag_s": r["fill_lag_s"],
                "n_fills": r["n_fills"], "n_rolls": r["n_rolls"],
                "executed": r["executed"], "net_return": r["net_return"],
                # context features
                "dir_short": float(r["direction"]),
                "dte_frac": dte / max(config.DTE_GRID),
                "prem_spot": (prem / spot) if (prem is not None and spot) else np.nan,
                "moneyness": np.log(strike / spot) if (strike and spot) else np.nan,
                "bars_since_signal": float(np.log1p(gaps[i])),
                **{k: frow.get(k, np.nan) for k in feats.columns},
            })
    return pd.DataFrame(all_rows)


# ── assembly ─────────────────────────────────────────────────────────────────

def assign_split(entry_date: pd.Series) -> pd.Series:
    d = entry_date
    return pd.Series(np.select(
        [(d >= config.TRAIN_START) & (d <= config.TRAIN_END),
         (d >= config.VAL_START) & (d <= config.VAL_END),
         (d >= config.TEST_START) & (d <= config.TEST_END)],
        ["train", "val", "test"], default="purged"), index=d.index)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=str, default=None)
    args = ap.parse_args()

    config.ensure_dirs()
    spec = load_spec()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] \
        if args.symbols else list(spec["symbols"])

    provider = HybridCachedProvider()
    frames = []
    for sym in symbols:
        if sym not in spec["symbols"]:
            print(f"[{sym}] not in baseline spec — skipped")
            continue
        print(f"[{sym}] building…", flush=True)
        df = build_symbol_rows(sym, spec["symbols"][sym], provider)
        if df.empty:
            print(f"[{sym}] no rows")
            continue
        ex_rate = df["executed"].mean()
        print(f"[{sym}] {len(df)} rows ({df['trade_idx'].nunique()} trades × "
              f"{df['dte'].nunique()} DTEs), executed {ex_rate:.0%}", flush=True)
        frames.append(df)

    if not frames:
        raise SystemExit("no rows built for any symbol")
    ds = pd.concat(frames, ignore_index=True)

    surface = load_surface_features()
    ds = join_surface_asof(ds, surface)

    ds["label"] = np.where(ds["net_return"].notna(),
                           (ds["net_return"].fillna(0) > 0).astype(float), np.nan)
    ds["split"] = assign_split(ds["entry_date"])
    ds = ds[ds["split"] != "purged"].reset_index(drop=True)

    # feature-timestamp hygiene: every feature is computed at the signal close,
    # which must never postdate the option fill used for the label
    filled = ds[ds["executed"] & ds["fill_lag_s"].notna()]
    assert (filled["fill_lag_s"] >= 0).all(), "option fill precedes signal bar"

    ds.to_parquet(config.META_DATASET_PARQUET, index=False)

    print(f"\ndataset: {len(ds)} rows → {config.META_DATASET_PARQUET}")
    lab = ds["label"].dropna()
    print(f"  labeled: {len(lab)} ({lab.mean():.1%} positive)")
    r = ds["net_return"].dropna()
    print(f"  net_return: mean {r.mean():+.3f} | p5 {r.quantile(.05):+.2f} | "
          f"p95 {r.quantile(.95):+.2f}")
    for s in ("train", "val", "test"):
        sub = ds[ds["split"] == s]
        n_lab = sub["label"].notna().sum()
        print(f"  {s:5s}: {len(sub):6d} rows | {n_lab:6d} labeled | "
              f"{sub['entry_date'].nunique():4d} days")
    nan_rates = ds[META_FEATURES].isna().mean()
    bad = nan_rates[nan_rates > 0.05]
    print(f"  feature NaN >5%: {'none' if bad.empty else bad.round(3).to_dict()}")


if __name__ == "__main__":
    main()
