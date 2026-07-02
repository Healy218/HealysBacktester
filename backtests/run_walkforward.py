# backtests/run_walkforward.py
"""
Walk-forward analysis module.

Splits historical data into rolling windows, optimizes parameters on each
in-sample (IS) window, and evaluates those exact parameters on the subsequent
out-of-sample (OOS) window.  Reports only OOS performance — the only honest
estimate of how a strategy would have performed on unseen data.

Anchored walk-forward with N folds:
  Fold 1:  IS = [0, 50%],  OOS = [50%, 67%]
  Fold 2:  IS = [0, 67%],  OOS = [67%, 83%]
  Fold 3:  IS = [0, 83%],  OOS = [83%, 100%]

The IS window expands with each fold (more training data) while each OOS
window is a fixed size covering fresh, unseen data.
"""

import gc
import numpy as np
import pandas as pd
from utils.logging_utils import setup_logging
from utils.chunked_runner import simulate_and_rank
from utils import freq_utils, runner_utils
from data import vbt_data_loader as data_loader, data_cleaner
from portfolio import simulator

logger = setup_logging(log_file="logs/backtester.log")

DEFAULT_N_FOLDS = 3
DEFAULT_MIN_TRAIN_PCT = 0.5


# ═══════════════════════════════════════════════════════════════════════════
#  Public entry point — same interface as other runners
# ═══════════════════════════════════════════════════════════════════════════

def run(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    backtest_config: dict,
    strategy_config: dict,
    progress_callback=None,
    *,
    inner_strategy: str = "MA Crossover",
    inner_strategy_config: dict | None = None,
    n_folds: int = DEFAULT_N_FOLDS,
    min_train_pct: float = DEFAULT_MIN_TRAIN_PCT,
) -> dict:
    """
    Walk-forward analysis wrapping any classical strategy.

    Returns the same dict structure as other runners:
      top5       — per-fold OOS results + an aggregate summary row
      error      — None on success, or an error message
      portfolio  — the last fold's OOS portfolio (for graphing)
      price_data — the last fold's OOS price data
    """
    try:
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        enable_shorting = backtest_config.get("ENABLE_SHORTING", False)
        strat_cfg = inner_strategy_config or strategy_config

        # ── 1. Load full-period data ────────────────────────────────────────
        logger.info(f"[WF] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        n_bars = len(price_data)
        oos_size = int(n_bars * (1 - min_train_pct) / n_folds)
        if oos_size < 30:
            return _err(
                f"Too few bars ({n_bars}) for {n_folds}-fold walk-forward. "
                f"Need more data or fewer folds."
            )

        # ── 2. Build fold boundaries ────────────────────────────────────────
        folds = []
        for k in range(n_folds):
            is_end = int(n_bars * min_train_pct) + k * oos_size
            oos_start = is_end
            oos_end = min(oos_start + oos_size, n_bars)
            if oos_end <= oos_start:
                break
            folds.append((0, is_end, oos_start, oos_end))

        logger.info(f"[WF] {len(folds)} folds, ~{oos_size} bars per OOS window")

        # ── 3. Walk-forward loop ────────────────────────────────────────────
        all_oos_results = []
        wf_folds = []          # per-fold OOS returns for the fold-breakdown chart
        last_oos_pf = None
        last_oos_price = None

        for fi, (is_s, is_e, oos_s, oos_e) in enumerate(folds):
            if progress_callback:
                progress_callback(fi, len(folds))

            is_data = price_data.iloc[is_s:is_e]
            oos_data = price_data.iloc[oos_s:oos_e]

            logger.info(
                f"[WF] Fold {fi+1}/{len(folds)}: "
                f"IS={len(is_data)} bars, OOS={len(oos_data)} bars"
            )

            # ── IS: full parameter sweep ────────────────────────────────────
            is_signals = _generate_signals(
                inner_strategy, is_data, strat_cfg, backtest_config,
            )
            if is_signals is None:
                logger.warning(f"[WF] Fold {fi+1}: IS signal generation failed, skipping.")
                continue

            entries, exits, se, sx = is_signals
            if entries is None or entries.empty or not entries.any().any():
                logger.warning(f"[WF] Fold {fi+1}: No IS entry signals, skipping.")
                continue

            sim_kw = _sim_kwargs(backtest_config)
            is_result = simulate_and_rank(
                price_data=is_data,
                entries=entries,
                exits=exits,
                short_entries=se if enable_shorting else None,
                short_exits=sx if enable_shorting else None,
                freq=freq,
                sim_kwargs=sim_kw,
                strategy_tag=f"WF-IS-F{fi+1}",
            )
            del entries, exits, se, sx
            gc.collect()

            if is_result.get("error") or not is_result.get("top5"):
                logger.warning(f"[WF] Fold {fi+1}: IS optimization failed, skipping.")
                continue

            is_best = is_result["top5"][0]  # Best Sharpe
            is_pf = is_result["portfolio"]
            is_col = is_pf.wrapper.columns[is_best["portfolio_col_int_idx"]]

            logger.info(
                f"[WF] Fold {fi+1}: IS best = {is_best['param_label']} "
                f"(Sharpe={is_best.get('sharpe_ratio', 'N/A')})"
            )
            del is_result, is_pf
            gc.collect()

            # ── OOS: generate signals, extract IS-winning column, simulate ──
            oos_signals = _generate_signals(
                inner_strategy, oos_data, strat_cfg, backtest_config,
            )
            if oos_signals is None:
                logger.warning(f"[WF] Fold {fi+1}: OOS signal generation failed, skipping.")
                continue

            oos_ent, oos_ext, oos_se, oos_sx = oos_signals

            # Extract only the IS-winning column
            try:
                col_ent = _extract_col(oos_ent, is_col)
                col_ext = _extract_col(oos_ext, is_col)
            except KeyError:
                logger.warning(f"[WF] Fold {fi+1}: IS-best column not in OOS signals, skipping.")
                del oos_ent, oos_ext, oos_se, oos_sx
                gc.collect()
                continue

            col_se = _try_extract_col(oos_se, is_col) if enable_shorting else None
            col_sx = _try_extract_col(oos_sx, is_col) if enable_shorting else None

            del oos_ent, oos_ext, oos_se, oos_sx
            gc.collect()

            oos_pf = simulator.run_backtest(
                price_df=oos_data,
                entries_series=col_ent,
                exits_series=col_ext,
                short_entries_series=col_se,
                short_exits_series=col_sx,
                frequency=freq,
                **sim_kw,
            )
            if oos_pf is None:
                logger.warning(f"[WF] Fold {fi+1}: OOS simulation failed, skipping.")
                continue

            # ── Collect OOS stats ───────────────────────────────────────────
            fold_row = _make_oos_row(
                oos_pf, fi, len(folds),
                is_best["param_label"],
                is_best.get("sharpe_ratio"),
                is_best.get("total_return_pct"),
                oos_data,
            )
            all_oos_results.append(fold_row)
            try:
                fold_returns = oos_pf.returns()
            except Exception:
                fold_returns = None
            wf_folds.append({
                "fold": fi + 1,
                "param_label": is_best["param_label"],
                "returns": fold_returns,
            })
            last_oos_pf = oos_pf
            last_oos_price = oos_data

        if not all_oos_results:
            return _err("Walk-forward produced no valid OOS results across any fold.")

        # ── 4. Aggregate summary row ────────────────────────────────────────
        returns = [r["total_return_pct"] for r in all_oos_results if r["total_return_pct"] is not None]
        sharpes = [r["sharpe_ratio"] for r in all_oos_results if r["sharpe_ratio"] is not None]
        drawdowns = [r["max_drawdown_pct"] for r in all_oos_results if r["max_drawdown_pct"] is not None]
        win_rates = [r["win_rate_pct"] for r in all_oos_results if r["win_rate_pct"] is not None]

        summary = {
            "ranked_by": "WF Average (OOS)",
            "portfolio_col_int_idx": 0,
            "param_label": f"{len(all_oos_results)}-fold walk-forward average",
            "total_return_pct": round(np.mean(returns), 4) if returns else None,
            "sharpe_ratio": round(np.mean(sharpes), 4) if sharpes else None,
            "max_drawdown_pct": round(np.mean(drawdowns), 4) if drawdowns else None,
            "win_rate_pct": round(np.mean(win_rates), 4) if win_rates else None,
            "best_trade_pct": None,
            "total_trades": sum(r["total_trades"] for r in all_oos_results),
        }
        all_oos_results.insert(0, summary)

        if progress_callback:
            progress_callback(len(folds), len(folds))

        avg_ret = summary["total_return_pct"] or 0
        avg_sh = summary["sharpe_ratio"] or 0
        logger.info(f"[WF] Complete. Avg OOS Return: {avg_ret:.2f}%, Avg OOS Sharpe: {avg_sh:.4f}")

        return {
            "top5": all_oos_results,
            "error": None,
            "portfolio": last_oos_pf,
            "price_data": last_oos_price if last_oos_price is not None else price_data,
            "wf_folds": wf_folds,
        }

    except Exception as e:
        logger.exception(f"[WF] Unexpected error: {e}")
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy adapter — maps strategy name → signal generation
# ═══════════════════════════════════════════════════════════════════════════

def _generate_signals(strategy_name, price_data, strat_cfg, bt_cfg):
    """
    Generate all parameter-combo signals for a strategy on the given price data.
    Returns (entries, exits, short_entries, short_exits) or None on failure.
    """
    try:
        enable_shorting = bt_cfg.get("ENABLE_SHORTING", False)
        close = price_data["Close"]

        if strategy_name == "MA Crossover":
            from signals import ma_crossover
            windows = np.arange(
                strat_cfg.get("MA_WINDOW_START", 2),
                strat_cfg.get("MA_WINDOW_END", 143),
                strat_cfg.get("MA_WINDOW_STEP", 1),
            )
            return ma_crossover.generate_ma_signals(
                close, windows, enable_shorting=enable_shorting,
            )

        elif strategy_name == "RSI Threshold":
            from signals import rsi_threshold
            rsi_w = np.arange(
                strat_cfg.get("RSI_WINDOW_START", 5),
                strat_cfg.get("RSI_WINDOW_END", 36),
                strat_cfg.get("RSI_WINDOW_STEP", 1),
                dtype=int,
            )
            entry_t = _linspace(strat_cfg, "ENTRY_THRESHOLD_START", "ENTRY_THRESHOLD_END", "ENTRY_THRESHOLD_STEP", (10.0, 49.0, 0.5))
            exit_t = _linspace(strat_cfg, "EXIT_THRESHOLD_START", "EXIT_THRESHOLD_END", "EXIT_THRESHOLD_STEP", (51.0, 90.0, 0.5))
            se_t = _linspace(strat_cfg, "SHORT_ENTRY_THRESHOLD_START", "SHORT_ENTRY_THRESHOLD_END", "SHORT_ENTRY_THRESHOLD_STEP", (65.0, 80.0, 1.0)) if enable_shorting else None
            sx_t = _linspace(strat_cfg, "SHORT_EXIT_THRESHOLD_START", "SHORT_EXIT_THRESHOLD_END", "SHORT_EXIT_THRESHOLD_STEP", (20.0, 35.0, 1.0)) if enable_shorting else None
            return rsi_threshold.generate_rsi_signals(
                close, window=rsi_w, entry_threshold=entry_t, exit_threshold=exit_t,
                enable_shorting=enable_shorting,
                short_entry_threshold=se_t, short_exit_threshold=sx_t,
            )

        elif strategy_name == "MACD Crossover":
            from signals import macd_signals
            fast = _arange_int(strat_cfg, "FAST_WINDOW_START", "FAST_WINDOW_END", "FAST_WINDOW_STEP", (3, 27, 3))
            slow = _arange_int(strat_cfg, "SLOW_WINDOW_START", "SLOW_WINDOW_END", "SLOW_WINDOW_STEP", (17, 42, 3))
            sig = _arange_int(strat_cfg, "SIGNAL_WINDOW_START", "SIGNAL_WINDOW_END", "SIGNAL_WINDOW_STEP", (3, 23, 1))
            return macd_signals.generate_macd_signals(
                close, fast_window=fast, slow_window=slow, signal_window=sig,
                short_entries=enable_shorting, short_exits=enable_shorting,
            )

        elif strategy_name == "Bollinger Bands":
            from signals import bbands_breakout
            windows = np.arange(
                strat_cfg.get("BBANDS_WINDOW_START", 10),
                strat_cfg.get("BBANDS_WINDOW_END", 51),
                strat_cfg.get("BBANDS_WINDOW_STEP", 2),
            )
            stds = np.arange(
                strat_cfg.get("BBANDS_STD_START", 1.0),
                strat_cfg.get("BBANDS_STD_END", 3.25),
                strat_cfg.get("BBANDS_STD_STEP", 0.25),
            )
            return bbands_breakout.generate_bbands_signals(
                close, windows, stds, enable_shorting=enable_shorting,
            )

        elif strategy_name == "Stochastic Crossover":
            from signals import stoch_crossover
            k_w = np.arange(strat_cfg.get("STOCH_K_START", 5), strat_cfg.get("STOCH_K_END", 21), strat_cfg.get("STOCH_K_STEP", 1))
            d_w = np.arange(strat_cfg.get("STOCH_D_START", 3), strat_cfg.get("STOCH_D_END", 10), strat_cfg.get("STOCH_D_STEP", 1))
            os_r = np.arange(strat_cfg.get("STOCH_OVERSOLD_START", 20), strat_cfg.get("STOCH_OVERSOLD_END", 21), strat_cfg.get("STOCH_OVERSOLD_STEP", 1))
            ob_r = np.arange(strat_cfg.get("STOCH_OVERBOUGHT_START", 80), strat_cfg.get("STOCH_OVERBOUGHT_END", 81), strat_cfg.get("STOCH_OVERBOUGHT_STEP", 1))
            return stoch_crossover.generate_stoch_signals(
                price_data["High"], price_data["Low"], close,
                k_w, d_w, oversold_range=os_r, overbought_range=ob_r,
                enable_shorting=enable_shorting,
            )

        elif strategy_name == "Elliott Wave / Fib":
            from signals import elliott_wave_signals
            so = np.arange(strat_cfg.get("SWING_ORDER_START", 3), strat_cfg.get("SWING_ORDER_END", 20), strat_cfg.get("SWING_ORDER_STEP", 1))
            fl = np.arange(strat_cfg.get("FIB_LEVEL_START", 0.236), strat_cfg.get("FIB_LEVEL_END", 0.800), strat_cfg.get("FIB_LEVEL_STEP", 0.01))
            ft = np.arange(strat_cfg.get("FIB_TOLERANCE_START", 0.005), strat_cfg.get("FIB_TOLERANCE_END", 0.050), strat_cfg.get("FIB_TOLERANCE_STEP", 0.005))
            return elliott_wave_signals.generate_elliott_wave_signals(
                price_data["High"], price_data["Low"], close,
                so, fl, ft, enable_shorting=enable_shorting,
            )

        elif strategy_name == "Volume Breakout":
            from signals import volume_breakout
            vw = np.arange(strat_cfg.get("VOLUME_WINDOW_START", 30), strat_cfg.get("VOLUME_WINDOW_END", 60), strat_cfg.get("VOLUME_WINDOW_STEP", 2), dtype=int)
            vm = _linspace(strat_cfg, "VOLUME_MULTIPLIER_START", "VOLUME_MULTIPLIER_END", "VOLUME_MULTIPLIER_STEP", (1.5, 2.0, 0.1))
            em = np.arange(strat_cfg.get("EXIT_MA_WINDOW_START", 45), strat_cfg.get("EXIT_MA_WINDOW_END", 90), strat_cfg.get("EXIT_MA_WINDOW_STEP", 1), dtype=int)
            return volume_breakout.generate_volume_signals(
                ohlcv_df=price_data,
                volume_window_range=vw,
                volume_multiplier_range=vm,
                exit_ma_window_range=em,
                confirm_price_increase=strat_cfg.get("CONFIRM_PRICE_INCREASE", False),
            )

        else:
            logger.error(f"[WF] Unsupported strategy for walk-forward: {strategy_name}")
            return None

    except Exception as e:
        logger.error(f"[WF] Signal generation failed for {strategy_name}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _extract_col(df, col_label):
    """Extract a single column from a signal DataFrame, return as 1-col DataFrame."""
    s = df[col_label]
    if isinstance(s, pd.Series):
        return s.to_frame(name=col_label)
    return s


def _try_extract_col(df, col_label):
    """Like _extract_col but returns None if column not found or df is None."""
    if df is None:
        return None
    try:
        return _extract_col(df, col_label)
    except (KeyError, TypeError):
        return None


def _make_oos_row(oos_pf, fold_idx, n_folds, param_label, is_sharpe, is_return_pct, oos_data):
    """Build a result row from an OOS portfolio."""
    def _safe(fn):
        try:
            v = fn()
            return float(v.iloc[0]) if hasattr(v, 'iloc') else float(v)
        except Exception:
            return np.nan

    ret = _safe(oos_pf.total_return)
    sharpe = _safe(oos_pf.sharpe_ratio)
    dd = _safe(oos_pf.max_drawdown)
    try:
        wr = _safe(oos_pf.trades.win_rate)
    except Exception:
        wr = np.nan
    try:
        bt = _safe(lambda: oos_pf.trades.returns.max() * 100)
    except Exception:
        bt = np.nan
    try:
        tc = int(_safe(oos_pf.trades.count))
    except Exception:
        tc = 0

    period_str = (
        f"{oos_data.index[0].strftime('%Y-%m-%d')} to "
        f"{oos_data.index[-1].strftime('%Y-%m-%d')}"
    )

    return {
        "ranked_by": f"Fold {fold_idx+1}/{n_folds} OOS ({period_str})",
        "portfolio_col_int_idx": 0,
        "param_label": param_label,
        "total_return_pct": round(ret * 100, 4) if not np.isnan(ret) else None,
        "sharpe_ratio": round(sharpe, 4) if not np.isnan(sharpe) else None,
        "max_drawdown_pct": round(abs(dd) * 100, 4) if not np.isnan(dd) else None,
        "win_rate_pct": round(wr * 100, 4) if not np.isnan(wr) else None,
        "best_trade_pct": round(bt, 4) if not np.isnan(bt) else None,
        "total_trades": tc,
        # Extra WF-specific fields (still JSON-safe)
        "is_sharpe": is_sharpe,
        "is_return_pct": is_return_pct,
    }


_arange_int = runner_utils.arange_int
_linspace = runner_utils.linspace


def _sim_kwargs(cfg, sl_stop=None, tp_stop=None):
    return runner_utils.sim_kwargs(cfg, sl_stop, tp_stop)


def _err(msg):
    return runner_utils.err(msg, "WF", logger)
