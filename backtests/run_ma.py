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
from utils.param_utils import top5_from_portfolio
from data import data_loader, data_cleaner
from signals import ma_crossover
from portfolio import simulator

logger = setup_logging(log_file="logs/backtester.log")


def run(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    backtest_config: dict,
    strategy_config: dict,
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

        # 3. Simulate
        logger.info("[MA] Running simulation…")
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=short_entries if enable_shorting else None,
            short_exits_series=short_exits if enable_shorting else None,
            frequency=freq,
            **_sim_kwargs(backtest_config, sl_stop, tp_stop),
        )
        if portfolio is None:
            return _err("Simulation returned no portfolio.")

        # 4. Rank
        logger.info("[MA] Ranking combinations…")
        top5 = top5_from_portfolio(portfolio, n=5)
        return {"top5": top5, "error": None, "portfolio": portfolio, "price_data": price_data}

    except Exception as e:
        logger.exception(f"[MA] Unexpected error: {e}")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _sl(cfg):
    pct = cfg.get("STOP_LOSS_PERCENT")
    return pct if cfg.get("USE_STOP_LOSS") and pct else None


def _tp(cfg):
    pct = cfg.get("TAKE_PROFIT_PERCENT")
    return pct if cfg.get("USE_TAKE_PROFIT") and pct else None


def _sim_kwargs(cfg, sl_stop, tp_stop):
    return dict(
        initial_capital=cfg.get("INITIAL_CAPITAL", 100_000.0),
        fees=cfg.get("FEES_PERCENT", 0.001),
        slippage=cfg.get("SLIPPAGE_PERCENT", 0.0005),
        size=cfg.get("DEFAULT_SIZE", 0.9),
        size_type=cfg.get("DEFAULT_SIZE_TYPE", "percent"),
        sl_stop=sl_stop,
        tp_stop=tp_stop,
    )


def _err(msg: str) -> dict:
    logger.warning(f"[MA] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
