# nn_meta/baseline.py
"""Frozen mechanical baseline: the leak-free reference the NN must beat.

Protocol (per underlying × proposal strategy, ALL choices on TRAIN data only):
  1. Parameter sweep for EVERY strategy in config.PROPOSAL_STRATEGIES on the
     TRAIN window's 15m bars — same signal generators, simulator, and sim
     config as the dashboard. Best Sharpe wins per strategy, subject to a
     trades-per-day ceiling and a minimum trade count.
  2. Each strategy's frozen trades are executed as options at each DTE in
     config.DTE_GRID through options/execution.py (same engine as the
     dashboard overlay). Best per-trade Sharpe picks that strategy's DTE.
  3. spec["symbols"][sym] = {"strategies": {strat: {params, dte, …}},
     "best_strategy": …} written to artifacts/baseline_spec.json — the ONLY
     baseline definition downstream.

``evaluate_baseline`` replays a frozen spec on any window (val / test /
walk-forward folds): signals are generated over the full series so MA warmup
uses pre-window bars, trades are filtered to entries inside the window, then
executed at the frozen DTE. A trade entered inside the window keeps its full
P&L even if it exits after the window's end (disclosed; identical convention
for baseline and NN, so comparisons stay fair).

Run:  python -m nn_meta.freeze_baseline [--symbols SPY,QQQ]
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from utils.logging_utils import setup_logging
from utils import freq_utils, runner_utils
from utils.chunked_runner import simulate_and_rank
from portfolio import simulator
from options.execution import Execution, extract_trades, execute_trade_returns, to_naive_utc
from nn_meta.providers import get_provider
from nn_meta import config, proposals

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-META-BASE"
_FREQ = freq_utils.resolve_freq(None, config.INTERVAL)
_SIM_KWARGS = runner_utils.sim_kwargs(config.SIM_CONFIG)


# ── data access ───────────────────────────────────────────────────────────────

def load_underlying_15m(symbol: str) -> pd.DataFrame:
    """RTH 15m OHLCV for one symbol (tz-naive UTC index), from the CLI cache."""
    if not config.UNDERLYING_15M_PARQUET.exists():
        raise FileNotFoundError(
            f"{config.UNDERLYING_15M_PARQUET} missing — run "
            f"`python -m nn_meta.download_data` first.")
    panel = pd.read_parquet(config.UNDERLYING_15M_PARQUET)
    sub = panel[panel["symbol"] == symbol.upper()]
    out = sub.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]
    return out.sort_index()


# ── signal generation for a single frozen param set ───────────────────────────

def propose_trades(bars: pd.DataFrame, strategy: str, params: dict,
                   sim_start: str, sim_end: str) -> list[tuple]:
    """Simulated (entry_ts, exit_ts, direction) trades for one frozen
    (strategy, params) pair.

    Signals are computed on the FULL series (indicator warmup uses bars before
    ``sim_start``), then simulation runs on the [sim_start, sim_end] slice with
    the frozen sim config — stops and the trend filter shape the timeline
    exactly as they would in the dashboard.
    """
    entries, exits, s_ent, s_ext = proposals.single_signals(strategy, bars, params)
    price = bars.loc[sim_start:sim_end]

    def _one(df):
        return df.loc[sim_start:sim_end] if df is not None else None

    pf = simulator.run_backtest(
        price_df=price,
        entries_series=_one(entries),
        exits_series=_one(exits),
        short_entries_series=_one(s_ent),
        short_exits_series=_one(s_ext),
        frequency=_FREQ,
        **_SIM_KWARGS,
    )
    if pf is None:
        return []
    cols = pf.wrapper.columns
    single = pf[cols[0]] if len(cols) else pf
    return extract_trades(single)


# ── step 1: parameter sweep on TRAIN ─────────────────────────────────────────

def sweep_train_params(symbol: str, bars: pd.DataFrame, strategy: str,
                       train_start: str = config.TRAIN_START,
                       train_end: str = config.TRAIN_END) -> Optional[dict]:
    """Best-Sharpe params for one proposal strategy on the train window,
    under the activity guards. Params come straight from the winning
    portfolio column (no label parsing)."""
    bars_hist = bars.loc[:train_end]
    price = bars.loc[train_start:train_end]
    assert price.index.max() <= pd.Timestamp(train_end) + pd.Timedelta(days=1), \
        "sweep touched data beyond train_end"
    if len(price) < 26 * 60:      # < ~60 trading days of 15m bars
        logger.warning(f"[{_TAG}] {symbol}: only {len(price)} train bars — skipping")
        return None

    entries, exits, s_ent, s_ext = proposals.sweep_signals(strategy, bars_hist)
    result = simulate_and_rank(
        price_data=price,
        entries=entries.loc[train_start:train_end],
        exits=exits.loc[train_start:train_end],
        short_entries=s_ent.loc[train_start:train_end] if s_ent is not None else None,
        short_exits=s_ext.loc[train_start:train_end] if s_ext is not None else None,
        freq=_FREQ,
        sim_kwargs=_SIM_KWARGS,
        strategy_tag=f"{_TAG}-{symbol}-{strategy}",
    )
    rows = result.get("top5") or []
    pf = result.get("portfolio")
    if result.get("error") or not rows or pf is None:
        logger.warning(f"[{_TAG}] {symbol}/{strategy}: sweep failed: "
                       f"{result.get('error')}")
        return None

    n_days = max(price.index.normalize().nunique(), 1)
    candidates = sorted(
        (r for r in rows if r.get("sharpe_ratio") is not None),
        key=lambda r: -r["sharpe_ratio"])
    pick, constrained = None, True
    for r in candidates:
        tpd = r.get("total_trades", 0) / n_days
        if r.get("total_trades", 0) >= config.MIN_TRAIN_TRADES \
                and tpd <= config.TRADES_PER_DAY_CEILING:
            pick = r
            break
    if pick is None and candidates:      # nothing satisfies the guards — disclose
        pick, constrained = candidates[0], False
        logger.warning(f"[{_TAG}] {symbol}/{strategy}: no sweep row met activity "
                       f"guards; falling back to raw best Sharpe")
    if pick is None:
        return None

    return {
        "strategy": strategy,
        "params": proposals.params_from_portfolio(pf, pick["portfolio_col_int_idx"]),
        "param_label": pick.get("param_label"),
        "train_sharpe": pick.get("sharpe_ratio"),
        "train_return_pct": pick.get("total_return_pct"),
        "train_trades": pick.get("total_trades"),
        "train_win_rate_pct": pick.get("win_rate_pct"),
        "trades_per_day": round(pick.get("total_trades", 0) / n_days, 3),
        "met_activity_guards": constrained,
    }


# ── step 2: DTE selection + evaluation helpers ───────────────────────────────

def equity_metrics(returns: list[float], f: float = config.POSITION_FRACTION) -> dict:
    """Sequential compounding of per-trade net returns at fraction ``f``."""
    r = np.asarray([x for x in returns if x is not None], dtype=float)
    if r.size == 0:
        return {"n": 0, "total_return": None, "max_drawdown": None,
                "win_rate": None, "mean_return": None, "per_trade_sharpe": None}
    eq = np.cumprod(1.0 + f * r)
    peak = np.maximum.accumulate(eq)
    return {
        "n": int(r.size),
        "total_return": float(eq[-1] - 1.0),
        "max_drawdown": float(((peak - eq) / peak).max()),
        "win_rate": float((r > 0).mean()),
        "mean_return": float(r.mean()),
        "per_trade_sharpe": float(r.mean() / r.std(ddof=1)) if r.size > 1 and r.std(ddof=1) > 0 else None,
    }


def top_k_contribution(returns: list[float], k: int = 3,
                       f: float = config.POSITION_FRACTION) -> dict:
    """How much of the compounded return the k largest trades account for.

    If ``total_ex_topk`` collapses relative to ``total``, the window's verdict
    rests on a handful of outlier trades — treat it as noise-dominated.
    """
    r = np.asarray([x for x in returns if x is not None], dtype=float)
    if r.size == 0:
        return {"total": None, "total_ex_topk": None, "k": k}
    total = float(np.prod(1.0 + f * r) - 1.0)
    keep = np.sort(r)[:-k] if r.size > k else np.array([])
    ex = float(np.prod(1.0 + f * keep) - 1.0) if keep.size else 0.0
    return {"total": total, "total_ex_topk": ex, "k": k}


def execute_at_dte(symbol: str, trades: list[tuple], bars: pd.DataFrame,
                   dte: int, provider, end_date: str,
                   ex: Optional[Execution] = None) -> tuple[list[dict], dict]:
    """Run the shared executor for a trade timeline at one DTE."""
    if ex is None:
        ex = Execution(symbol, config.INTERVAL, end_date, provider, config.EXEC_CONFIG)
    und_close = bars["Close"]
    und_idx = pd.DatetimeIndex([to_naive_utc(t) for t in bars.index])
    return execute_trade_returns(
        ex, trades, und_close, und_idx, dte,
        fees=config.FEES_PERCENT, slippage=config.SLIPPAGE_PERCENT)


def choose_dte(per_dte: dict[int, dict]) -> Optional[int]:
    """Best per-trade Sharpe among DTEs with enough executed, well-filled trades."""
    def ok(d):
        s = per_dte[d]
        return s["n"] >= config.MIN_KEPT_TRADES and s["fill_fail_rate"] <= 0.4
    eligible = [d for d in per_dte if ok(d) and per_dte[d]["per_trade_sharpe"] is not None]
    if eligible:
        return max(eligible, key=lambda d: per_dte[d]["per_trade_sharpe"])
    executed = [d for d in per_dte if per_dte[d]["n"] > 0]
    return max(executed, key=lambda d: per_dte[d]["n"]) if executed else None


# ── freeze + evaluate ─────────────────────────────────────────────────────────

def _freeze_one_strategy(symbol: str, strategy: str, bars: pd.DataFrame,
                         provider, train_start: str, train_end: str
                         ) -> Optional[dict]:
    swp = sweep_train_params(symbol, bars, strategy, train_start, train_end)
    if swp is None:
        return None
    trades = propose_trades(bars, strategy, swp["params"], train_start, train_end)
    if len(trades) > config.MAX_SIGNALS_PER_NAME:
        logger.warning(f"[{_TAG}] {symbol}/{strategy}: {len(trades)} trades "
                       f"exceeds cap, truncating")
        trades = trades[:config.MAX_SIGNALS_PER_NAME]
    if not trades:
        return None
    assert all(to_naive_utc(t[1]) <= pd.Timestamp(train_end) + pd.Timedelta(days=1)
               for t in trades), "train trade leaked beyond train_end"

    # One Execution shared across the DTE grid (chain/bars caches are common).
    ex = Execution(symbol, config.INTERVAL, train_end, provider,
                   config.EXEC_CONFIG)
    per_dte: dict[int, dict] = {}
    for dte in config.DTE_GRID:
        records, meta = execute_at_dte(symbol, trades, bars.loc[:train_end],
                                       dte, provider, train_end, ex=ex)
        stats = equity_metrics([r["net_return"] for r in records if r["executed"]])
        stats["fill_fail_rate"] = meta["fill_fail_rate"]
        stats["n_rolls"] = meta["n_rolls"]
        per_dte[dte] = stats

    best = choose_dte(per_dte)
    if best is None:
        return None
    return {
        **swp, "dte": best,
        "train_option": {str(d): per_dte[d] for d in per_dte},
        "n_train_signals": len(trades),
    }


def freeze_symbol(symbol: str, provider,
                  train_start: str = config.TRAIN_START,
                  train_end: str = config.TRAIN_END) -> Optional[dict]:
    """Freeze every proposal strategy for one symbol; mark the train-best."""
    bars = load_underlying_15m(symbol)
    if bars.empty:
        logger.warning(f"[{_TAG}] {symbol}: no 15m bars")
        return None

    strategies: dict[str, dict] = {}
    for strat in config.PROPOSAL_STRATEGIES:
        try:
            entry = _freeze_one_strategy(symbol, strat, bars, provider,
                                         train_start, train_end)
        except Exception as e:
            logger.exception(f"[{_TAG}] {symbol}/{strat}: freeze failed: {e}")
            entry = None
        if entry is not None:
            strategies[strat] = entry
    if not strategies:
        return None

    def _score(s):
        st = strategies[s]["train_option"][str(strategies[s]["dte"])]
        return st["per_trade_sharpe"] if st["per_trade_sharpe"] is not None else -np.inf

    return {"strategies": strategies,
            "best_strategy": max(strategies, key=_score)}


def evaluate_baseline(symbol: str, spec_entry: dict, window: tuple[str, str],
                      provider, bars: Optional[pd.DataFrame] = None) -> dict:
    """Frozen baseline P&L on an arbitrary window: every strategy's proposals
    at its own frozen params/DTE, pooled chronologically."""
    if bars is None:
        bars = load_underlying_15m(symbol)
    start, end = window
    lo, hi = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    all_records: list[dict] = []
    n_signals = 0
    for strat, entry in spec_entry["strategies"].items():
        all_trades = propose_trades(bars, strat, entry["params"],
                                    config.WINDOW_START, config.WINDOW_END)
        trades = [t for t in all_trades if lo <= to_naive_utc(t[0]) < hi]
        if not trades:
            continue
        n_signals += len(trades)
        records, _ = execute_at_dte(symbol, trades, bars, entry["dte"],
                                    provider, config.WINDOW_END)
        all_records.extend(r for r in records if r["executed"])
    all_records.sort(key=lambda r: r["fill_entry_ts"])
    metrics = equity_metrics([r["net_return"] for r in all_records])
    metrics["n_signals"] = n_signals
    return {"metrics": metrics, "records": all_records}


# ── spec I/O ─────────────────────────────────────────────────────────────────

def _config_hash() -> str:
    frozen = {
        "interval": config.INTERVAL, "dte_grid": config.DTE_GRID,
        "strategies": config.PROPOSAL_STRATEGIES,
        "grids": config.SWEEP_GRIDS,
        "sim": config.SIM_CONFIG, "train": [config.TRAIN_START, config.TRAIN_END],
        "ceiling": config.TRADES_PER_DAY_CEILING,
        "min_trades": config.MIN_TRAIN_TRADES,
    }
    return hashlib.md5(json.dumps(frozen, sort_keys=True).encode()).hexdigest()[:12]


def load_spec() -> dict:
    if not config.BASELINE_SPEC_JSON.exists():
        raise FileNotFoundError(
            f"{config.BASELINE_SPEC_JSON} missing — run "
            f"`python -m nn_meta.freeze_baseline` first.")
    spec = json.loads(config.BASELINE_SPEC_JSON.read_text())
    first = next(iter(spec.get("symbols", {}).values()), None)
    if first is not None and "strategies" not in first:
        raise ValueError("baseline_spec.json is the v1 (MA-only) schema — "
                         "re-run `python -m nn_meta.freeze_baseline`.")
    if spec.get("config_hash") != _config_hash():
        logger.warning(f"[{_TAG}] baseline_spec config hash mismatch — the spec was "
                       f"frozen under different settings; consider re-freezing")
    return spec


def freeze_all(symbols: Optional[list[str]] = None, out_path=None) -> dict:
    config.ensure_dirs()
    provider = get_provider()
    from pathlib import Path
    dest = Path(out_path or config.BASELINE_SPEC_JSON)

    # resume: reload a partial spec and skip already-frozen symbols. Combined
    # with the per-symbol write below, a killed/rebooted freeze picks up where
    # it stopped instead of losing everything.
    if dest.exists():
        out = json.loads(dest.read_text())
        out.setdefault("symbols", {})
        done = set(out["symbols"]) | set(out.get("skipped", []))
        if done:
            print(f"resuming: {len(done)} symbols already done in {dest.name}",
                  flush=True)
    else:
        out = {
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "interval": config.INTERVAL,
            "train_window": [config.TRAIN_START, config.TRAIN_END],
            "dte_grid": config.DTE_GRID,
            "symbols": {}, "skipped": [],
        }
        out["config_hash"] = _config_hash()
        done = set()

    for sym in (symbols or config.UNDERLYINGS):
        if sym in done:
            continue
        print(f"[{sym}] sweeping…", flush=True)
        try:
            entry = freeze_symbol(sym, provider)
        except Exception as e:
            logger.exception(f"[{_TAG}] {sym}: freeze failed: {e}")
            entry = None
        if entry is None:
            print(f"[{sym}] SKIPPED (no freezable baseline)")
            out.setdefault("skipped", []).append(sym)
        else:
            out["symbols"][sym] = entry
            for strat, e in entry["strategies"].items():
                t = e["train_option"][str(e["dte"])]
                star = "*" if strat == entry["best_strategy"] else " "
                print(f"[{sym}] {star}{strat:8s} {e['param_label'][:38]:38s} "
                      f"dte={e['dte']:>2d} | n={t['n']:3d} win={t['win_rate']:.0%} "
                      f"ret={t['total_return']:+.1%} "
                      f"(fills ok {1 - t['fill_fail_rate']:.0%})", flush=True)
        dest.write_text(json.dumps(out, indent=2))   # checkpoint per symbol

    print(f"\nfroze {len(out['symbols'])} symbols → {dest}")
    return out


def merge_specs(shard_paths: list, out_path=None) -> dict:
    """Combine sharded freeze specs' symbol dicts into one baseline_spec."""
    from pathlib import Path
    merged = None
    for p in shard_paths:
        s = json.loads(Path(p).read_text())
        if merged is None:
            merged = {k: v for k, v in s.items()
                      if k not in ("symbols", "skipped")}
            merged["symbols"], merged["skipped"] = {}, []
        merged["symbols"].update(s.get("symbols", {}))
        merged["skipped"].extend(s.get("skipped", []))
    dest = out_path or config.BASELINE_SPEC_JSON
    Path(dest).write_text(json.dumps(merged, indent=2))
    print(f"merged {len(shard_paths)} shards → {len(merged['symbols'])} "
          f"symbols → {dest}")
    return merged
    return out
