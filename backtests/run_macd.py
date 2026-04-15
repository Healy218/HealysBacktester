# backtests/run_macd.py
"""
MACD Crossover backtest runner.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils
from utils.chunked_runner import simulate_and_rank
from data import vbt_data_loader as data_loader, data_cleaner
from signals import macd_signals

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
    Runs the MACD Crossover parameter sweep and returns the top-5 combinations.
    See run_ma.py for return dict structure.
    """
    try:
        freq    = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)

        fast_windows   = _arange_int(strategy_config, "FAST_WINDOW_START",   "FAST_WINDOW_END",   "FAST_WINDOW_STEP",   (3,  27, 3))
        slow_windows   = _arange_int(strategy_config, "SLOW_WINDOW_START",   "SLOW_WINDOW_END",   "SLOW_WINDOW_STEP",   (17, 42, 3))
        signal_windows = _arange_int(strategy_config, "SIGNAL_WINDOW_START", "SIGNAL_WINDOW_END", "SIGNAL_WINDOW_STEP", (3,  23, 1))

        if any(a.size == 0 for a in [fast_windows, slow_windows, signal_windows]):
            return _err("One or more MACD parameter ranges is empty. Check settings.")

        enable_shorts = backtest_config.get("ENABLE_SHORTING", False)

        # 1. Data
        logger.info(f"[MACD] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        # 2. Signals (macd_signals filters fast >= slow internally)
        logger.info(f"[MACD] Generating signals…")
        entries, exits, short_entries, short_exits = macd_signals.generate_macd_signals(
            close_prices_series=price_data["Close"],
            fast_window=fast_windows,
            slow_window=slow_windows,
            signal_window=signal_windows,
            short_entries=enable_shorts,
            short_exits=enable_shorts,
        )
        if entries is None or entries.empty:
            return _err("No entry signals generated.")

        # 3. Simulate + Rank (chunked for large sweeps)
        logger.info("[MACD] Running simulation…")
        return simulate_and_rank(
            price_data=price_data,
            entries=entries,
            exits=exits,
            short_entries=short_entries if enable_shorts else None,
            short_exits=short_exits if enable_shorts else None,
            freq=freq,
            sim_kwargs=_sim_kwargs(backtest_config, sl_stop, tp_stop),
            strategy_tag="MACD",
            progress_callback=progress_callback,
        )

    except Exception as e:
        logger.exception(f"[MACD] Unexpected error: {e}")
        return _err(str(e))


def _arange_int(cfg, sk, ek, stk, default):
    s, e, st = default
    return np.arange(cfg.get(sk, s), cfg.get(ek, e), cfg.get(stk, st), dtype=int)


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


def _err(msg):
    logger.warning(f"[MACD] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
