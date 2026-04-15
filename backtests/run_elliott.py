# backtests/run_elliott.py
"""
Elliott Wave / Fibonacci Retracement backtest runner.
Callable from the dashboard — same interface as run_ma, run_rsi, etc.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils
from utils.chunked_runner import simulate_and_rank
from data import vbt_data_loader as data_loader, data_cleaner
from signals import elliott_wave_signals

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
    Runs the Elliott Wave parameter sweep and returns top-5 combinations.
    """
    try:
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)
        enable_shorting = backtest_config.get("ENABLE_SHORTING", False)

        # Build parameter ranges
        so_start = strategy_config.get("SWING_ORDER_START", 3)
        so_end = strategy_config.get("SWING_ORDER_END", 20)
        so_step = strategy_config.get("SWING_ORDER_STEP", 1)
        swing_orders = np.arange(so_start, so_end, so_step)

        fl_start = strategy_config.get("FIB_LEVEL_START", 0.236)
        fl_end = strategy_config.get("FIB_LEVEL_END", 0.800)
        fl_step = strategy_config.get("FIB_LEVEL_STEP", 0.01)
        fib_levels = np.arange(fl_start, fl_end, fl_step)

        ft_start = strategy_config.get("FIB_TOLERANCE_START", 0.005)
        ft_end = strategy_config.get("FIB_TOLERANCE_END", 0.050)
        ft_step = strategy_config.get("FIB_TOLERANCE_STEP", 0.005)
        fib_tolerances = np.arange(ft_start, ft_end, ft_step)

        if swing_orders.size < 1 or fib_levels.size < 1 or fib_tolerances.size < 1:
            return _err("Elliott Wave parameter ranges are empty.")

        n_combos = swing_orders.size * fib_levels.size * fib_tolerances.size
        logger.info(f"[ELLIOTT] {n_combos:,} parameter combinations")

        # 1. Data
        logger.info(f"[ELLIOTT] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'. Check the ticker and date range.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        # 2. Signals
        logger.info(f"[ELLIOTT] Generating signals ({n_combos:,} combinations)...")
        entries, exits, short_entries, short_exits = elliott_wave_signals.generate_elliott_wave_signals(
            price_data["High"],
            price_data["Low"],
            price_data["Close"],
            swing_orders,
            fib_levels,
            fib_tolerances,
            enable_shorting=enable_shorting,
        )
        if entries is None or entries.empty or not entries.any().any():
            return _err("No entry signals generated. Try a wider date range or different parameters.")

        # 3. Simulate + Rank (chunked for large sweeps)
        logger.info("[ELLIOTT] Running simulation...")
        return simulate_and_rank(
            price_data=price_data,
            entries=entries,
            exits=exits,
            short_entries=short_entries if enable_shorting else None,
            short_exits=short_exits if enable_shorting else None,
            freq=freq,
            sim_kwargs=_sim_kwargs(backtest_config, sl_stop, tp_stop),
            strategy_tag="ELLIOTT",
            progress_callback=progress_callback,
        )

    except Exception as e:
        logger.exception(f"[ELLIOTT] Unexpected error: {e}")
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
        trend_filter_window=cfg.get("TREND_FILTER_WINDOW", 0),
        atr_sl_window=cfg.get("ATR_SL_WINDOW"),
        atr_sl_multiplier=cfg.get("ATR_SL_MULTIPLIER", 2.0),
        use_trailing_stop=cfg.get("USE_TRAILING_STOP", False),
    )


def _err(msg: str) -> dict:
    logger.warning(f"[ELLIOTT] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
