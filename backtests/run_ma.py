# backtests/run_ma.py
"""
Moving Average Crossover backtest runner.
Callable from the dashboard — returns top-5 results as a JSON-serializable dict
and stores the live portfolio + price data in the shared _last_run cache.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils.error_handling import DataError, SignalError, PortfolioError
from utils import freq_utils
from utils.chunked_runner import simulate_and_rank
from utils import runner_utils
from data import vbt_data_loader as data_loader, data_cleaner
from signals import ma_crossover

logger = setup_logging(log_file="logs/backtester.log")


def run(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    backtest_config: dict,
    strategy_config: dict,
    progress_callback=None,
) -> dict:
    """
    Runs the MA Crossover parameter sweep and returns the top-5 combinations.

    Returns a dict with keys:
      "top5"      — list of dicts (JSON-serializable), sorted by Sharpe desc.
      "error"     — None on success, or an error message string.
      "portfolio" — live vectorbt Portfolio object (NOT JSON-safe, store separately).
      "price_data"— cleaned OHLCV DataFrame (NOT JSON-safe, store separately).
    """
    try:
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)
        enable_shorting = backtest_config.get("ENABLE_SHORTING", False)

        # Build MA window range
        ma_start = strategy_config.get("MA_WINDOW_START", 2)
        ma_end   = strategy_config.get("MA_WINDOW_END",   143)
        ma_step  = strategy_config.get("MA_WINDOW_STEP",  1)
        windows  = np.arange(ma_start, ma_end, ma_step)
        if windows.size < 2:
            return _err("MA window range is too small (need at least 2 values).")

        # 1. Data
        logger.info(f"[MA] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'. Check the ticker and date range.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        # 2. Signals
        n_combos = windows.size * (windows.size - 1) // 2
        logger.info(f"[MA] Generating signals ({n_combos:,} combinations)…")
        entries, exits, short_entries, short_exits = ma_crossover.generate_ma_signals(
            price_data["Close"], windows, enable_shorting=enable_shorting
        )
        if entries is None or entries.empty or not entries.any().any():
            return _err("No entry signals generated. Try a wider date range or different interval.")

        # 3. Simulate + Rank (chunked for large sweeps)
        logger.info("[MA] Running simulation…")
        return simulate_and_rank(
            price_data=price_data,
            entries=entries,
            exits=exits,
            short_entries=short_entries if enable_shorting else None,
            short_exits=short_exits if enable_shorting else None,
            freq=freq,
            sim_kwargs=_sim_kwargs(backtest_config, sl_stop, tp_stop),
            strategy_tag="MA",
            progress_callback=progress_callback,
        )

    except Exception as e:
        logger.exception(f"[MA] Unexpected error: {e}")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_sl = runner_utils.sl_stop
_tp = runner_utils.tp_stop


def _sim_kwargs(cfg, sl_stop=None, tp_stop=None):
    return runner_utils.sim_kwargs(cfg, sl_stop, tp_stop)


def _err(msg):
    return runner_utils.err(msg, "MA", logger)
