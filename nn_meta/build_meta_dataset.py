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
from nn_meta.providers import get_provider
from nn_meta import config
from nn_meta.baseline import (load_underlying_15m, load_spec, propose_trades,
                              execute_at_dte)
from nn_meta.feature_contract import v4_feature_names

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-META-DS"

# Feature list (single source of truth — train / select / runner import this).
META_FEATURES = [
    # 15m technicals at the signal bar close
    "ma_gap", "px_vs_fast", "rsi14", "macd_hist", "bb_z",
    "ret_1", "ret_8", "ret_26", "session_gap", "gap_abs_z", "tod", "dow",
    "is_first_hour", "is_last_hour", "dow_tod",
    # daily option-surface state, as-of previous close
    "rvol_5", "rvol_21", "atm_iv_near", "atm_iv_far",
    "term_slope", "iv_chg_5", "pc_ratio",
    # market/cross-sectional context (v2.1)
    "market_iv", "rv_iv_spread", "beta_60d",
    # trade context
    "dir_short", "dte_frac", "prem_spot", "moneyness", "bars_since_signal",
    # proposal-strategy one-hots
    *[f"strat_{s}" for s in config.PROPOSAL_STRATEGIES],
    # sector one-hots
    *[f"sec_{g}" for g in config.SECTOR_GROUPS],
]

# V4 model runs use only features available at the signal close.  Keep this
# separate from META_FEATURES until v2/v3 deployed model bundles are retired:
# their persisted scalers deliberately reference the legacy schema.
V4_META_FEATURES = v4_feature_names(META_FEATURES)


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

    # |gap| z-score vs trailing 60 sessions: an earnings/shock-recency proxy
    # (a true earnings calendar needs a data source we don't have offline).
    daily_gap = session_gap.groupby(day).first()
    gz = (daily_gap.abs() - daily_gap.abs().rolling(60).mean()) \
        / daily_gap.abs().rolling(60).std().replace(0, np.nan)
    gap_abs_z = day.map(gz)

    bar_of_day = pd.Series(bars.groupby(day).cumcount().values, index=bars.index)
    tod = bar_of_day / 26.0
    dow = pd.Series(bars.index.dayofweek, index=bars.index) / 4.0

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
        "gap_abs_z": gap_abs_z,
        "tod": tod,
        "dow": dow,
        "is_first_hour": (bar_of_day <= 3).astype(float),
        "is_last_hour": (bar_of_day >= 22).astype(float),
        "dow_tod": dow * tod,
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

def _feature_windows(strategy: str, params: dict) -> tuple[int, int]:
    """(fast, slow) for the ma_gap / px_vs_fast features. MA uses its own
    frozen windows; other strategies use the dashboard's 10/30 convention so
    trend context stays comparable across proposal streams."""
    if strategy == "ma":
        return int(params["fast_window"]), int(params["slow_window"])
    return 10, 30


def build_symbol_rows(symbol: str, spec_entry: dict, provider,
                      window_start: str = config.WINDOW_START,
                      window_end: str = config.WINDOW_END) -> pd.DataFrame:
    bars = load_underlying_15m(symbol)
    if bars.empty:
        logger.warning(f"[{_TAG}] {symbol}: no bars")
        return pd.DataFrame()
    close = bars["Close"]

    frames = []
    for strat, entry in spec_entry["strategies"].items():
        trades = propose_trades(bars, strat, entry["params"],
                                window_start, window_end)
        if len(trades) > config.MAX_SIGNALS_PER_NAME:
            logger.warning(f"[{_TAG}] {symbol}/{strat}: truncating "
                           f"{len(trades)} trades to cap")
            trades = trades[:config.MAX_SIGNALS_PER_NAME]
        if not trades:
            continue

        f_w, s_w = _feature_windows(strat, entry["params"])
        feats = technical_features(bars, f_w, s_w)

        entry_ts = [to_naive_utc(t[0]) for t in trades]
        entry_pos = bars.index.searchsorted(entry_ts)
        gaps = np.diff(entry_pos, prepend=entry_pos[0])

        ex = Execution(symbol, config.INTERVAL, window_end, provider,
                       config.EXEC_CONFIG)
        rows = []
        for dte in config.DTE_GRID:
            records, meta = execute_at_dte(symbol, trades, bars, dte, provider,
                                           window_end, ex=ex)
            logger.info(f"[{_TAG}] {symbol}/{strat} {dte}DTE: "
                        f"{meta['n_executed']}/{meta['n_signals']} executed, "
                        f"{meta['n_rolls']} rolls")
            for i, r in enumerate(records):
                ts = to_naive_utc(r["entry_ts"])
                xs = to_naive_utc(r["exit_ts"])
                hist = close.loc[:ts]
                spot = float(hist.iloc[-1]) if len(hist) else np.nan
                exit_hist = close.loc[:xs]
                und_ret = (float(exit_hist.iloc[-1]) / spot - 1) \
                    if (len(exit_hist) and spot) else np.nan
                f = feats.loc[:ts]
                frow = f.iloc[-1] if len(f) else pd.Series(index=feats.columns,
                                                           dtype=float)
                prem, strike = r["entry_premium"], r["strike"]
                rows.append({
                    "symbol": symbol, "strategy": strat,
                    "trade_idx": r["trade_idx"], "dte": dte,
                    "entry_ts": ts, "entry_date": ts.normalize(),
                    "exit_ts": xs,
                    "direction": r["direction"], "right": r["right"],
                    "contract": r["contract"], "strike": strike,
                    "expiration": r["expiration"],
                    "entry_premium": prem, "fill_lag_s": r["fill_lag_s"],
                    # Execution provenance retained for V4 accounting.  The
                    # current dataset has no intratrade marks, so it cannot
                    # itself claim mark-to-market accounting.
                    "fill_entry_ts": r.get("fill_entry_ts"),
                    "fill_exit_ts": r.get("fill_exit_ts"),
                    "gross_return": r.get("gross_return"),
                    "n_fills": r["n_fills"], "n_rolls": r["n_rolls"],
                    "executed": r["executed"], "net_return": r["net_return"],
                    "und_period_return": und_ret,
                    # context features
                    "dir_short": float(r["direction"]),
                    "dte_frac": dte / max(config.DTE_GRID),
                    "prem_spot": (prem / spot) if (prem is not None and spot) else np.nan,
                    "moneyness": np.log(strike / spot) if (strike and spot) else np.nan,
                    "bars_since_signal": float(np.log1p(gaps[i])),
                    **{k: frow.get(k, np.nan) for k in feats.columns},
                })
        frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ── cross-sectional context (v2.1) ───────────────────────────────────────────

def rolling_beta_60d() -> pd.DataFrame:
    """Per-(underlying, date) rolling 60d beta vs SPY from daily closes."""
    und = pd.read_parquet(config.UNDERLYING_DAILY_PARQUET,
                          columns=["underlying", "date", "close"])
    px = und.pivot(index="date", columns="underlying", values="close").sort_index()
    rets = px.pct_change()
    spy = rets["SPY"]
    cov = rets.rolling(60).cov(spy)
    beta = cov.div(spy.rolling(60).var(), axis=0)
    out = beta.stack().rename("beta_60d").reset_index()
    out.columns = ["date", "underlying", "beta_60d"]
    return out


def add_context_features(ds: pd.DataFrame, surface: pd.DataFrame) -> pd.DataFrame:
    """market_iv (SPY ATM IV as-of prev close), rv_iv_spread, beta_60d,
    strategy + sector one-hots. Runs AFTER join_surface_asof."""
    ds = ds.sort_values("entry_date").reset_index(drop=True)

    spy_iv = surface[surface["underlying"] == "SPY"][["date", "atm_iv_near"]] \
        .rename(columns={"atm_iv_near": "market_iv"}).sort_values("date")
    ds = pd.merge_asof(ds, spy_iv, left_on="entry_date", right_on="date",
                       allow_exact_matches=False).drop(columns=["date"])

    ds["rv_iv_spread"] = ds["rvol_21"] - ds["atm_iv_near"]

    beta = rolling_beta_60d().sort_values("date")
    parts = []
    for sym, grp in ds.groupby("symbol"):
        b = beta[beta["underlying"] == sym].drop(columns=["underlying"])
        if b.empty:
            grp = grp.copy()
            grp["beta_60d"] = np.nan
            parts.append(grp)
            continue
        parts.append(pd.merge_asof(grp.sort_values("entry_date"), b,
                                   left_on="entry_date", right_on="date",
                                   allow_exact_matches=False)
                     .drop(columns=["date"]))
    ds = pd.concat(parts, ignore_index=True)

    for s in config.PROPOSAL_STRATEGIES:
        ds[f"strat_{s}"] = (ds["strategy"] == s).astype(float)
    sector = ds["symbol"].map(config.SECTOR_MAP)
    for g in config.SECTOR_GROUPS:
        ds[f"sec_{g}"] = (sector == g).astype(float)
    return ds


# ── assembly ─────────────────────────────────────────────────────────────────

def assign_split(entry_date: pd.Series) -> pd.Series:
    d = entry_date
    return pd.Series(np.select(
        [(d >= config.TRAIN_START) & (d <= config.TRAIN_END),
         (d >= config.VAL_START) & (d <= config.VAL_END),
         (d >= config.TEST_START) & (d <= config.TEST_END)],
        ["train", "val", "test"], default="purged"), index=d.index)


ROWS_DIR = config.ARTIFACTS / "meta_rows"     # per-symbol checkpoint dir


def build_rows(symbols, spec, provider, rows_dir=ROWS_DIR) -> None:
    """Build each symbol's raw rows into rows_dir/<sym>.parquet, skipping any
    already present. Resumable AND shardable: parallel workers on disjoint
    symbol subsets write to the same dir without collision (surface join,
    labels and split are applied later in assemble()). Empty results write a
    0-row marker so a re-run doesn't rebuild a genuinely empty symbol."""
    rows_dir.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        if sym not in spec["symbols"]:
            print(f"[{sym}] not in baseline spec — skipped")
            continue
        pq = rows_dir / f"{sym}.parquet"
        if pq.exists():
            print(f"[{sym}] cached — skip")
            continue
        print(f"[{sym}] building…", flush=True)
        df = build_symbol_rows(sym, spec["symbols"][sym], provider)
        tmp = pq.with_suffix(".tmp")               # atomic: no truncated checkpoints
        df.to_parquet(tmp, index=False)             # 0-row df writes a marker
        tmp.replace(pq)
        if df.empty:
            print(f"[{sym}] no rows")
        else:
            print(f"[{sym}] {len(df)} rows ({df['strategy'].nunique()} "
                  f"strategies, {df['dte'].nunique()} DTEs), "
                  f"executed {df['executed'].mean():.0%}", flush=True)


def assemble(rows_dir=ROWS_DIR) -> None:
    """Concat all per-symbol rows → surface join → labels → split → write."""
    parts = sorted(rows_dir.glob("*.parquet"))
    if not parts:
        raise SystemExit(f"no per-symbol rows in {rows_dir} — build first")
    frames = [d for d in (pd.read_parquet(p) for p in parts) if not d.empty]
    if not frames:
        raise SystemExit("all per-symbol frames are empty")
    ds = pd.concat(frames, ignore_index=True)

    surface = load_surface_features()
    ds = join_surface_asof(ds, surface)
    ds = add_context_features(ds, surface)

    labeled = ds["net_return"].notna()
    ds["label"] = np.where(labeled, (ds["net_return"].fillna(0) > 0).astype(float),
                           np.nan)
    excess_ok = labeled & ds["und_period_return"].notna()
    ds["label_excess"] = np.where(
        excess_ok,
        (ds["net_return"].fillna(0) > ds["und_period_return"].fillna(0)).astype(float),
        np.nan)
    ds["split"] = assign_split(ds["entry_date"])
    ds = ds[ds["split"] != "purged"].reset_index(drop=True)

    # feature-timestamp hygiene: every feature is computed at the signal close,
    # which must never postdate the option fill used for the label
    filled = ds[ds["executed"] & ds["fill_lag_s"].notna()]
    assert (filled["fill_lag_s"] >= 0).all(), "option fill precedes signal bar"

    ds.to_parquet(config.META_DATASET_PARQUET, index=False)

    print(f"\ndataset: {len(ds)} rows → {config.META_DATASET_PARQUET}")
    lab = ds["label"].dropna()
    lab_x = ds["label_excess"].dropna()
    print(f"  label win:    {len(lab)} ({lab.mean():.1%} positive)")
    print(f"  label excess: {len(lab_x)} ({lab_x.mean():.1%} positive)")
    r = ds["net_return"].dropna()
    print(f"  net_return: mean {r.mean():+.3f} | p5 {r.quantile(.05):+.2f} | "
          f"p95 {r.quantile(.95):+.2f}")
    by_strat = ds[ds["executed"]].groupby("strategy").size()
    print("  executed rows by strategy: "
          + ", ".join(f"{s}={n}" for s, n in by_strat.items()))
    for s in ("train", "val", "test"):
        sub = ds[ds["split"] == s]
        n_lab = sub["label"].notna().sum()
        print(f"  {s:5s}: {len(sub):6d} rows | {n_lab:6d} labeled | "
              f"{sub['entry_date'].nunique():4d} days")
    nan_rates = ds[META_FEATURES].isna().mean()
    bad = nan_rates[nan_rates > 0.05]
    print(f"  feature NaN >5%: {'none' if bad.empty else bad.round(3).to_dict()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=str, default=None,
                    help="comma-separated subset (for sharded parallel builds)")
    ap.add_argument("--assemble", action="store_true",
                    help="concat the per-symbol rows into the final dataset")
    args = ap.parse_args()
    config.ensure_dirs()
    if args.assemble:
        assemble()
        return
    spec = load_spec()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] \
        if args.symbols else list(spec["symbols"])
    build_rows(symbols, spec, get_provider())
    print(f"\nbuilt per-symbol rows for {len(symbols)} symbols → {ROWS_DIR}\n"
          f"run `--assemble` to concat into the dataset")


if __name__ == "__main__":
    main()
