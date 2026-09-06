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
import json

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
from nn_meta import mark_stream

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


def _write_partial(path, df: pd.DataFrame) -> None:
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def _provenance(entry, grid, start=config.WINDOW_START, end=config.WINDOW_END):
    from nn_meta.feature_contract import CONTRACT_VERSION
    return {"version": CONTRACT_VERSION, "entry": entry, "grid": sorted(grid),
            "window": [start, end], "execution": config.EXEC_CONFIG,
            "sim": config.SIM_CONFIG, "fees": config.FEES_PERCENT,
            "slippage": config.SLIPPAGE_PERCENT}


def _provenance_path(path):
    return path.with_suffix(".provenance.json")


def _write_provenance(path, value):
    dest = _provenance_path(path)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True))
    tmp.replace(dest)


def _read_provenance(path):
    try:
        return json.loads(_provenance_path(path).read_text())
    except (OSError, ValueError):
        return None


def _marks_cover(rows, marks):
    if rows.empty:
        return True
    executed = rows[rows["executed"].fillna(False).astype(bool)]
    if executed.empty:
        return True
    if marks is None or marks.empty:
        return False
    if not set(mark_stream.PERSISTED_COLUMNS) <= set(marks.columns):
        return False
    normalized = mark_stream.validate_mark_stream(marks)
    ids = mark_stream.stable_trade_id(executed)
    if not set(ids) <= set(normalized["trade_id"].astype(str)):
        return False
    if {"fill_entry_ts", "fill_exit_ts"} <= set(executed.columns):
        bounds = normalized.groupby("trade_id", observed=True)["mark_ts"].agg(["min", "max"])
        for tid, row in zip(ids, executed.itertuples()):
            if bounds.loc[tid, "min"] != pd.Timestamp(row.fill_entry_ts) \
                    or bounds.loc[tid, "max"] != pd.Timestamp(row.fill_exit_ts):
                return False
    return True


def build_symbol_rows(symbol: str, spec_entry: dict, provider,
                      window_start: str = config.WINDOW_START,
                      window_end: str = config.WINDOW_END,
                      marks_sink: list | None = None,
                      partial_dir=None,
                      dte_grid: list[int] | None = None,
                      reuse: tuple[pd.DataFrame, pd.DataFrame | None] | None = None
                      ) -> pd.DataFrame:
    """Build one symbol's raw rows.

    Passing ``marks_sink`` (a list) additionally collects per-contract 15m mark
    frames into it — the Option B mark-to-market input.  It is a sink rather
    than a second return value so the three existing callers keep working
    unchanged.

    ``partial_dir`` (2026-09-01) enables per-FAMILY checkpointing: a v5
    symbol is ~8h of work (10 families x DTE grid) and a spot preemption used
    to lose all of it — the family is the natural ~30-60min grain. Each
    completed family writes ``<sym>.<strat>.rows.parquet`` (+ ``.marks``)
    atomically; a rerun loads those and skips straight to the first
    unfinished family. Empty families write 0-row markers.
    """
    bars = load_underlying_15m(symbol)
    if bars.empty:
        logger.warning(f"[{_TAG}] {symbol}: no bars")
        return pd.DataFrame()
    close = bars["Close"]
    dte_grid = list(dte_grid or config.DTE_GRID)

    # ``reuse`` (2026-09-05, additive generations): (rows, marks) of this symbol
    # from an EARLIER pool built under the same window/grid. Families present
    # there are taken as-is (rows + their marks) and not rebuilt, so a pool
    # that only ADDS families builds only the new ones.
    reuse_rows = reuse[0] if reuse is not None and reuse[0] is not None else None
    reuse_marks = reuse[1] if reuse is not None else None

    frames = []
    for strat, entry in spec_entry["strategies"].items():
        if reuse_rows is not None and (reuse_rows["strategy"] == strat).any() \
                and (marks_sink is None or _marks_cover(
                    reuse_rows[reuse_rows["strategy"] == strat], reuse_marks)):
            sub = reuse_rows[reuse_rows["strategy"] == strat].reset_index(drop=True)
            frames.append(sub)
            if marks_sink is not None and reuse_marks is not None and not reuse_marks.empty:
                from nn_meta import mark_stream as _ms
                keep = set(_ms.stable_trade_id(sub))
                m = reuse_marks[reuse_marks["trade_id"].astype(str).isin(keep)]
                if not m.empty:
                    marks_sink.append(m.reset_index(drop=True))
            logger.info(f"[{_TAG}] {symbol}/{strat}: reused {len(sub)} rows from "
                        f"the earlier pool")
            continue
        p_rows = p_marks = None
        if partial_dir is not None:
            p_rows = partial_dir / f"{symbol}.{strat}.rows.parquet"
            p_marks = partial_dir / f"{symbol}.{strat}.marks.parquet"
            provenance = _provenance(entry, dte_grid, window_start, window_end)
            # A rows partial WITHOUT its marks partial is an INCOMPLETE
            # checkpoint, not a marks-free family: the writer always emits
            # the marks file first (empty frame included), but the bucket
            # transport is not atomic across files — task.sh pushes with a
            # parallel `rsync` every 4 min and pulls with `cp <sym>.* || true`,
            # either of which can be cut in half by a spot preemption.
            # Resuming such a family would commit rows whose trades have NO
            # entries in the mark stream, and assemble's keep_ids filter would
            # silently accept the under-covered sidecar — the 2026-08-19
            # biased-drop failure mode wearing a different hat. Rebuild it.
            if p_rows.exists() and (_read_provenance(p_rows) != provenance
                    or (marks_sink is not None and (not p_marks.exists()
                        or not _marks_cover(pd.read_parquet(p_rows),
                                            pd.read_parquet(p_marks))))):
                logger.warning(f"[{_TAG}] {symbol}/{strat}: rows partial has "
                               f"no marks partial — incomplete checkpoint, "
                               f"rebuilding the family")
                p_rows.unlink(missing_ok=True)
            elif p_rows.exists():
                pdf = pd.read_parquet(p_rows)
                if not pdf.empty:
                    frames.append(pdf)
                if marks_sink is not None:
                    pmf = pd.read_parquet(p_marks)
                    if not pmf.empty:
                        marks_sink.append(pmf)
                logger.info(f"[{_TAG}] {symbol}/{strat}: resumed from "
                            f"partial ({len(pdf)} rows)")
                continue
        sink_before = len(marks_sink) if marks_sink is not None else 0
        trades = propose_trades(bars, strat, entry["params"],
                                window_start, window_end)
        if len(trades) > config.MAX_SIGNALS_PER_NAME:
            logger.warning(f"[{_TAG}] {symbol}/{strat}: truncating "
                           f"{len(trades)} trades to cap")
            trades = trades[:config.MAX_SIGNALS_PER_NAME]
        if not trades:
            if p_rows is not None:
                if marks_sink is not None:
                    _write_partial(p_marks, pd.DataFrame())
                _write_partial(p_rows, pd.DataFrame())
                _write_provenance(p_rows, provenance)
            continue

        f_w, s_w = _feature_windows(strat, entry["params"])
        feats = technical_features(bars, f_w, s_w)

        entry_ts = [to_naive_utc(t[0]) for t in trades]
        entry_pos = bars.index.searchsorted(entry_ts)
        gaps = np.diff(entry_pos, prepend=entry_pos[0])

        ex = Execution(symbol, config.INTERVAL, window_end, provider,
                       config.EXEC_CONFIG)
        rows = []
        for dte in dte_grid:
            records, meta = execute_at_dte(symbol, trades, bars, dte, provider,
                                           window_end, ex=ex,
                                           collect_marks=marks_sink is not None)
            if marks_sink is not None and meta.get("blotter"):
                # Key the marks exactly as the rows below will be keyed, so the
                # sidecar joins back to the dataset without a trade_id column.
                keyed = pd.DataFrame({
                    "symbol": symbol, "strategy": strat,
                    "trade_idx": [r["trade_idx"] for r in records],
                    "dte": dte,
                    "entry_ts": [to_naive_utc(r["entry_ts"]) for r in records],
                })
                tids = mark_stream.stable_trade_id(keyed)
                m = mark_stream.marks_from_blotter(
                    meta["blotter"],
                    dict(zip(keyed["trade_idx"].astype(int), tids)))
                if not m.empty:
                    marks_sink.append(m)
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
                    # Execution provenance retained for V4 accounting; the
                    # matching intratrade marks come from --marks.
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
                    # Target ATM moneyness is knowable at decision time.
                    # Executed strike remains provenance, never a feature.
                    "moneyness": float(np.log1p(config.EXEC_CONFIG.get("MONEYNESS", 0.0))),
                    "bars_since_signal": float(np.log1p(gaps[i])),
                    **{k: frow.get(k, np.nan) for k in feats.columns},
                })
        fam_df = pd.DataFrame(rows)
        frames.append(fam_df)
        if p_rows is not None:
            # marks before rows, mirroring build_rows' commit order: a rows
            # partial must never exist without the marks that price it.
            if marks_sink is not None:
                new_marks = marks_sink[sink_before:]
                _write_partial(p_marks,
                               pd.concat(new_marks, ignore_index=True)
                               if new_marks else pd.DataFrame())
            _write_partial(p_rows, fam_df)
            _write_provenance(p_rows, provenance)
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
MARKS_DIR = config.ARTIFACTS / "meta_marks"   # per-symbol mark-stream shards


def _reusable_rows(sym: str, spec_entry: dict, pool: str, marks: bool,
                   dte_grid: list[int] | None = None):
    """(rows, marks) from ``nn_meta/artifacts_<pool>/`` restricted to the
    families whose FROZEN ENTRY (params + dte) is identical in both specs — a
    re-frozen family (e.g. a weekly-expiry name whose grid changed) must be
    rebuilt, not reused. Returns None when nothing is reusable."""
    rdir = config.ROOT / f"artifacts_{pool}"
    rp, mp, sp = (rdir / "meta_rows" / f"{sym}.parquet",
                  rdir / "meta_marks" / f"{sym}.parquet", rdir / "baseline_spec.json")
    if not rp.exists() or not sp.exists():
        return None
    grid = list(dte_grid or config.DTE_GRID)
    recorded = _read_provenance(rp)
    expected = _provenance(spec_entry, grid)
    if recorded is None or any(recorded.get(k) != v for k, v in expected.items()
                               if k not in ("entry", "grid")):
        return None
    import json as _json
    old_entry = _json.loads(sp.read_text()).get("symbols", {}).get(sym)
    if not old_entry or recorded.get("entry") != old_entry:
        return None
    same = [st for st, e in spec_entry["strategies"].items()
            if st in old_entry.get("strategies", {})
            and old_entry["strategies"][st].get("params") == e.get("params")
            and old_entry["strategies"][st].get("dte") == e.get("dte")]
    if not same:
        return None
    rows = pd.read_parquet(rp)
    rows = rows[rows["strategy"].isin(same)].reset_index(drop=True)
    complete = [st for st, g in rows.groupby("strategy")
                if set(g["dte"]) == set(grid)]
    rows = rows[rows["strategy"].isin(complete)].reset_index(drop=True)
    if rows.empty:
        return None
    mk = pd.read_parquet(mp) if (marks and mp.exists()) else None
    if marks and not _marks_cover(rows, mk):
        return None
    logger.info(f"[{_TAG}] {sym}: reusable families from {pool}: {same}")
    return (rows, mk)


def build_rows(symbols, spec, provider, rows_dir=ROWS_DIR,
               marks: bool = False, marks_dir=MARKS_DIR,
               partial_dir=None, reuse_from: str | None = None) -> None:
    """Build each symbol's raw rows into rows_dir/<sym>.parquet, skipping any
    already present. Resumable AND shardable: parallel workers on disjoint
    symbol subsets write to the same dir without collision (surface join,
    labels and split are applied later in assemble()). Empty results write a
    0-row marker so a re-run doesn't rebuild a genuinely empty symbol."""
    rows_dir.mkdir(parents=True, exist_ok=True)
    if marks:
        marks_dir.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        if sym not in spec["symbols"]:
            print(f"[{sym}] not in baseline spec — skipped")
            continue
        pq = rows_dir / f"{sym}.parquet"
        from nn_meta.weekly_expiry import dte_grid_for
        grid = dte_grid_for(sym, spec)
        provenance = _provenance(spec["symbols"][sym], grid)
        mpq = marks_dir / f"{sym}.parquet"
        if pq.exists() and _read_provenance(pq) == provenance and (not marks
                or (mpq.exists() and _marks_cover(pd.read_parquet(pq), pd.read_parquet(mpq)))):
            print(f"[{sym}] cached — skip")
            continue
        print(f"[{sym}] building…", flush=True)
        sink = [] if marks else None
        reuse = None
        if reuse_from:
            reuse = _reusable_rows(sym, spec["symbols"][sym], reuse_from, marks, grid)
        df = build_symbol_rows(sym, spec["symbols"][sym], provider,
                               marks_sink=sink, partial_dir=partial_dir,
                               dte_grid=grid, reuse=reuse)
        if marks:
            # validate per symbol so a malformed shard surfaces here, not hours
            # later at assemble; also restores the categorical key after concat
            mdf = mark_stream.validate_mark_stream(
                pd.concat(sink, ignore_index=True)) if sink else \
                pd.DataFrame({c: [] for c in mark_stream.PERSISTED_COLUMNS})
            mpq = marks_dir / f"{sym}.parquet"
            mtmp = mpq.with_suffix(".tmp")
            mdf.to_parquet(mtmp, index=False)
            mtmp.replace(mpq)                       # marks land before the rows
        tmp = pq.with_suffix(".tmp")               # atomic: no truncated checkpoints
        df.to_parquet(tmp, index=False)             # 0-row df writes a marker
        tmp.replace(pq)
        _write_provenance(pq, provenance)
        if partial_dir is not None:
            # the committed symbol parquet supersedes its family partials
            for p in partial_dir.glob(f"{sym}.*.parquet"):
                p.unlink(missing_ok=True)
        if df.empty:
            print(f"[{sym}] no rows")
        else:
            print(f"[{sym}] {len(df)} rows ({df['strategy'].nunique()} "
                  f"strategies, {df['dte'].nunique()} DTEs), "
                  f"executed {df['executed'].mean():.0%}", flush=True)


def assemble(rows_dir=ROWS_DIR, marks_dir=MARKS_DIR,
             membership: bool = False) -> None:
    """Concat all per-symbol rows → surface join → labels → split → write.

    With membership=True (the v5 default), rows are first filtered to
    (symbol, entry month) pairs where the symbol was a point-in-time universe
    member — per the frozen monthlies, loud if none exist.

    When per-symbol mark shards exist they are concatenated into the sidecar
    beside the dataset, filtered to the rows that survived the split purge.
    """
    parts = sorted(rows_dir.glob("*.parquet"))
    if not parts:
        raise SystemExit(f"no per-symbol rows in {rows_dir} — build first")
    expected = _provenance({}, config.DTE_GRID)
    for part in parts:
        recorded = _read_provenance(part)
        if recorded is None or any(recorded.get(k) != v for k, v in expected.items()
                                   if k not in ("entry", "grid")):
            raise SystemExit(f"stale or unversioned rows: {part} — rebuild before assembling")
    frames = [d for d in (pd.read_parquet(p) for p in parts) if not d.empty]
    if not frames:
        raise SystemExit("all per-symbol frames are empty")
    if marks_dir.exists() and any(marks_dir.glob("*.parquet")):
        for part in parts:
            rows = pd.read_parquet(part)
            mp = marks_dir / part.name
            marks = pd.read_parquet(mp) if mp.exists() else None
            if not _marks_cover(rows, marks):
                raise SystemExit(f"incomplete marks for {part.name} — rebuild with --marks")
    spec = load_spec()
    from nn_meta.weekly_expiry import dte_grid_for
    for part in parts:
        entry = spec.get("symbols", {}).get(part.stem)
        if entry is None or _read_provenance(part) != _provenance(
                entry, dte_grid_for(part.stem, spec)):
            raise SystemExit(f"rows disagree with current frozen spec/grid: {part} — rebuild")
    ds = pd.concat(frames, ignore_index=True)

    if membership:
        from nn_meta.universe_pit import membership_mask
        keep = membership_mask(ds["symbol"], ds["entry_date"])
        print(f"membership: kept {int(keep.sum())}/{len(ds)} rows "
              f"({(~keep).sum()} outside point-in-time membership)")
        ds = ds[keep].reset_index(drop=True)
        if ds.empty:
            raise SystemExit("membership filter left no rows — check the "
                             "frozen months against the build window")

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
    from nn_meta.feature_contract import CONTRACT_VERSION, baseline_spec_fingerprint
    ds.attrs["feature_contract_version"] = CONTRACT_VERSION
    ds.attrs["baseline_spec_sha256"] = baseline_spec_fingerprint(spec)

    # feature-timestamp hygiene: every feature is computed at the signal close,
    # which must never postdate the option fill used for the label
    filled = ds[ds["executed"] & ds["fill_lag_s"].notna()]
    assert (filled["fill_lag_s"] >= 0).all(), "option fill precedes signal bar"

    tmp = config.META_DATASET_PARQUET.with_suffix(".tmp")   # atomic: this is a
    ds.to_parquet(tmp, index=False)                         # committed artifact
    tmp.replace(config.META_DATASET_PARQUET)

    mark_parts = sorted(marks_dir.glob("*.parquet")) if marks_dir.exists() else []
    if mark_parts:
        # streamed shard-by-shard on purpose — the full stream is ~88M rows and
        # does not fit in memory as one frame (see write_mark_stream_shards)
        dest, n_marks, n_traded = mark_stream.write_mark_stream_shards(
            mark_parts, mark_stream.mark_stream_path(config.META_DATASET_PARQUET),
            keep_ids=mark_stream.stable_trade_id(ds))
        print(f"marks:   {n_marks} rows over {n_traded} trades → {dest}")

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
    ap.add_argument("--marks", action="store_true",
                    help="also emit the per-contract 15m mark stream (Option B)")
    ap.add_argument("--membership", action=argparse.BooleanOptionalAction,
                    default=(config.POOL in ("v5", "v6")),
                    help="restrict assemble to point-in-time universe members "
                         "per (symbol, month) — default ON for v5/v6 pools")
    ap.add_argument("--reuse-rows-from", default=None, metavar="POOL",
                    help="additive build: take families already built for this "
                         "symbol in nn_meta/artifacts_<POOL>/ (rows + marks) and "
                         "build only the missing ones (same window/grid required)")
    ap.add_argument("--partial-dir", type=str, default=None,
                    help="enable per-family intra-symbol checkpoints in this "
                         "dir (spot-preemption resume; see build_symbol_rows)")
    args = ap.parse_args()
    config.ensure_dirs()
    if args.assemble:
        assemble(membership=args.membership)
        return
    spec = load_spec()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] \
        if args.symbols else list(spec["symbols"])
    partial_dir = None
    if args.partial_dir:
        from pathlib import Path
        partial_dir = Path(args.partial_dir)
        partial_dir.mkdir(parents=True, exist_ok=True)
    build_rows(symbols, spec, get_provider(), marks=args.marks,
               partial_dir=partial_dir, reuse_from=args.reuse_rows_from)
    print(f"\nbuilt per-symbol rows for {len(symbols)} symbols → {ROWS_DIR}\n"
          f"run `--assemble` to concat into the dataset")


if __name__ == "__main__":
    main()
