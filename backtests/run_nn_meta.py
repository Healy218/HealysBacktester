# backtests/run_nn_meta.py
"""NN Meta Filter runner — the frozen MA baseline vs its NN-filtered version.

Dashboard-callable (same API as every run_*.py). For the requested window:
  1. Frozen params from nn_meta/artifacts/baseline_spec.json propose trades
     (same simulator semantics used to freeze them).
  2. Each trade is executed as an option at the frozen DTE (cache-first
     provider) to obtain decision-time context features (contract, premium).
  3. The nn_meta/model_final ensemble scores each proposal; trades with
     mean P(win) >= threshold are kept.
  4. TWO columns are simulated on the underlying and returned side by side:
     "Baseline (all trades)" and "NN-filtered" — the top-5 table becomes the
     head-to-head. Stops/trend-filter are OFF in this re-simulation: the
     frozen timeline already encodes them.

v1 supports the 15m interval only — the meta-features are 15m-native
(time-of-day, bar-based returns); other intervals would silently shift the
feature distributions the scaler was fit on.

With Asset Type = Options, the dashboard overlay wraps this runner and
re-executes the better column's trades across its DTE grid (exploratory view);
nn_meta/select_meta.py remains the honest frozen-DTE evaluation.
"""
import json

import numpy as np
import pandas as pd

from utils.logging_utils import setup_logging
from utils import freq_utils, runner_utils, param_utils
from data import vbt_data_loader
from portfolio import simulator

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-META-RUN"

BASELINE_COL = "Baseline (all)"
FILTERED_COL = "NN-filtered"


def _err(msg):
    return runner_utils.err(msg, _TAG, logger)


def _signal_frames(index: pd.Index, trades: list, kept: list[bool]):
    """Two-column boolean entry/exit frames (long + short) from trade lists."""
    cols = [BASELINE_COL, FILTERED_COL]
    ent = pd.DataFrame(False, index=index, columns=cols)
    ext = pd.DataFrame(False, index=index, columns=cols)
    s_ent = pd.DataFrame(False, index=index, columns=cols)
    s_ext = pd.DataFrame(False, index=index, columns=cols)
    for (e_ts, x_ts, direction), keep in zip(trades, kept):
        targets = [BASELINE_COL] + ([FILTERED_COL] if keep else [])
        for col in targets:
            if direction == 0:
                ent.loc[e_ts, col] = True
                ext.loc[x_ts, col] = True
            else:
                s_ent.loc[e_ts, col] = True
                s_ext.loc[x_ts, col] = True
    return ent, ext, s_ent, s_ext


def run(symbol, start_date, end_date, interval, backtest_config, strategy_config,
        progress_callback=None) -> dict:
    cb = progress_callback or (lambda i, n: None)
    try:
        if interval != "15m":
            return _err("NN Meta Filter supports the 15m interval only — its "
                        "features are 15m-native. Select Interval: 15 Minutes.")

        # Heavy imports deferred so the dashboard boots without TensorFlow.
        from nn_meta import config as mcfg
        from nn_meta.baseline import load_spec, propose_trades, execute_at_dte
        from nn_meta.build_meta_dataset import (META_FEATURES, technical_features,
                                                load_surface_features, _SURFACE_COLS)
        from nn_meta.download_data import filter_rth
        from nn_meta.train_meta import prepare_matrix
        from nn_meta.select_meta import predict_rows
        from nn_meta.providers import get_provider
        from options.execution import to_naive_utc

        ens_path = mcfg.MODEL_FINAL_DIR / "ensemble_config.json"
        if not ens_path.exists():
            return _err("No trained meta-model bundle. Run the nn_meta pipeline "
                        "(freeze_baseline → build_meta_dataset → train_meta → "
                        "select_meta) first.")
        ens = json.loads(ens_path.read_text())
        spec = load_spec()
        if symbol not in spec["symbols"]:
            return _err(f"'{symbol}' has no frozen baseline "
                        f"(available: {', '.join(sorted(spec['symbols']))}).")
        entry = spec["symbols"][symbol]

        cb(10, 100)
        raw = vbt_data_loader.load_price_data_smart(symbol, start_date, end_date,
                                                    interval)
        if raw is None or raw.empty:
            return _err(f"Could not load 15m data for '{symbol}'.")
        bars = filter_rth(raw[["Open", "High", "Low", "Close", "Volume"]])

        trades = propose_trades(bars, entry["fast"], entry["slow"],
                                start_date, end_date)
        if not trades:
            return _err("Frozen baseline produced no trades in this window.")
        cb(30, 100)

        # ── execute at frozen DTE for context features ────────────────────────
        provider = get_provider()
        records, meta = execute_at_dte(symbol, trades, bars, entry["dte"],
                                       provider, end_date)
        cb(55, 100)

        # ── feature rows (decision-time observables) ──────────────────────────
        feats = technical_features(bars, entry["fast"], entry["slow"])
        close = bars["Close"]
        entry_pos = bars.index.searchsorted([to_naive_utc(t[0]) for t in trades])
        gaps = np.diff(entry_pos, prepend=entry_pos[0])
        rows = []
        for i, r in enumerate(records):
            ts = to_naive_utc(r["entry_ts"])
            spot = float(close.loc[:ts].iloc[-1]) if len(close.loc[:ts]) else np.nan
            f = feats.loc[:ts]
            frow = f.iloc[-1] if len(f) else pd.Series(dtype=float)
            prem, strike = r["entry_premium"], r["strike"]
            rows.append({
                "symbol": symbol, "entry_ts": ts,
                "entry_date": ts.normalize(),
                "dir_short": float(r["direction"]),
                "dte_frac": entry["dte"] / max(mcfg.DTE_GRID),
                "prem_spot": (prem / spot) if (prem and spot) else np.nan,
                "moneyness": np.log(strike / spot) if (strike and spot) else np.nan,
                "bars_since_signal": float(np.log1p(gaps[i])),
                **{k: frow.get(k, np.nan) for k in feats.columns},
            })
        frows = pd.DataFrame(rows)
        surface = load_surface_features()
        s = surface[surface["underlying"] == symbol]
        if not s.empty:
            frows = pd.merge_asof(frows.sort_values("entry_date"),
                                  s.drop(columns=["underlying"]),
                                  left_on="entry_date", right_on="date",
                                  allow_exact_matches=False).drop(columns=["date"])
        else:
            for c in _SURFACE_COLS:
                frows[c] = np.nan
        frows = frows.sort_values("entry_ts").reset_index(drop=True)

        # ── ensemble filter ───────────────────────────────────────────────────
        preds = np.mean([predict_rows(rid, frows) for rid in ens["run_ids"]], axis=0)
        kept = (preds >= ens["threshold"]).tolist()
        cb(75, 100)
        logger.info(f"[{_TAG}] {symbol}: {sum(kept)}/{len(trades)} proposals kept "
                    f"(thr={ens['threshold']}, fills ok {1 - meta['fill_fail_rate']:.0%})")

        # ── simulate both columns (timeline already encodes stops/filter) ────
        sim_kwargs = runner_utils.sim_kwargs(backtest_config, None, None)
        sim_kwargs.update(sl_stop=None, tp_stop=None, trend_filter_window=0)
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        ent, ext, s_ent, s_ext = _signal_frames(bars.index, trades, kept)
        pf = simulator.run_backtest(
            price_df=bars, entries_series=ent, exits_series=ext,
            short_entries_series=s_ent, short_exits_series=s_ext,
            frequency=freq, **sim_kwargs)
        if pf is None:
            return _err("Simulation returned nothing.")
        cb(95, 100)

        rows_out = []
        for k, name in enumerate([FILTERED_COL, BASELINE_COL]):
            idx = list(pf.wrapper.columns).index(name)
            row = param_utils._make_row_from_index(pf, idx, name)
            row["param_label"] = (
                f"{name} — fast={entry['fast']} slow={entry['slow']} "
                f"dte={entry['dte']}"
                + (f" | kept {sum(kept)}/{len(trades)}" if name == FILTERED_COL else ""))
            rows_out.append(row)
        rows_out.sort(key=lambda r: (r.get("sharpe_ratio") is None,
                                     -(r.get("sharpe_ratio") or 0)))
        for k, row in enumerate(rows_out, start=1):
            row["ranked_by"] = "Best Sharpe" if k == 1 else f"Sharpe #{k}"
        cb(100, 100)
        return {"top5": rows_out, "error": None, "portfolio": pf, "price_data": bars}

    except Exception as e:
        logger.exception(f"[{_TAG}] Unexpected error: {e}")
        return _err(str(e))
