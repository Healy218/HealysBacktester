# backtests/run_rsi.py
"""
RSI Threshold backtest runner.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils
from utils.chunked_runner import simulate_and_rank
from data import vbt_data_loader as data_loader, data_cleaner
from signals import rsi_threshold

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
    Runs the RSI Threshold parameter sweep and returns the top-5 combinations.
    See run_ma.py for return dict structure.
    """
    try:
        freq   = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)

        # Build parameter ranges
        rsi_windows = _arange_int(
            strategy_config, "RSI_WINDOW_START", "RSI_WINDOW_END", "RSI_WINDOW_STEP",
            default=(5, 36, 1),
        )
        entry_thresholds = _linspace_float(
            strategy_config,
            "ENTRY_THRESHOLD_START", "ENTRY_THRESHOLD_END", "ENTRY_THRESHOLD_STEP",
            default=(10.0, 49.0, 0.5),
        )
        exit_thresholds = _linspace_float(
            strategy_config,
            "EXIT_THRESHOLD_START", "EXIT_THRESHOLD_END", "EXIT_THRESHOLD_STEP",
            default=(51.0, 90.0, 0.5),
        )

        enable_shorting = backtest_config.get("ENABLE_SHORTING", False)
        short_entry_range = short_exit_range = None
        if enable_shorting:
            short_entry_range = _linspace_float(
                strategy_config,
                "SHORT_ENTRY_THRESHOLD_START", "SHORT_ENTRY_THRESHOLD_END",
                "SHORT_ENTRY_THRESHOLD_STEP", default=(65.0, 80.0, 1.0),
            )
            short_exit_range = _linspace_float(
                strategy_config,
                "SHORT_EXIT_THRESHOLD_START", "SHORT_EXIT_THRESHOLD_END",
                "SHORT_EXIT_THRESHOLD_STEP", default=(20.0, 35.0, 1.0),
            )

        if any(a.size == 0 for a in [rsi_windows, entry_thresholds, exit_thresholds]):
            return _err("One or more RSI parameter ranges is empty. Check settings.")

        # 1. Data
        logger.info(f"[RSI] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        # 2. Signals
        n_combos = rsi_windows.size * entry_thresholds.size * exit_thresholds.size
        logger.info(f"[RSI] Generating signals (~{n_combos:,} combos)…")
        entries, exits, short_entries, short_exits = rsi_threshold.generate_rsi_signals(
            close_prices_series=price_data["Close"],
            window=rsi_windows,
            entry_threshold=entry_thresholds,
            exit_threshold=exit_thresholds,
            enable_shorting=enable_shorting,
            short_entry_threshold=short_entry_range,
            short_exit_threshold=short_exit_range,
        )
        if entries is None or entries.empty:
            return _err("No entry signals generated.")

        # 3. Simulate + Rank (chunked for large sweeps)
        logger.info("[RSI] Running simulation…")
        return simulate_and_rank(
            price_data=price_data,
            entries=entries,
            exits=exits,
            short_entries=short_entries if enable_shorting else None,
            short_exits=short_exits if enable_shorting else None,
            freq=freq,
            sim_kwargs=_sim_kwargs(backtest_config, sl_stop, tp_stop),
            strategy_tag="RSI",
            progress_callback=progress_callback,
        )

    except Exception as e:
        logger.exception(f"[RSI] Unexpected error: {e}")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arange_int(cfg, start_key, end_key, step_key, default):
    s, e, st = default
    arr = np.arange(
        cfg.get(start_key, s),
        cfg.get(end_key,   e),
        cfg.get(step_key,  st),
        dtype=int,
    )
    return arr


def _linspace_float(cfg, start_key, end_key, step_key, default):
    s, e, st = default
    start = cfg.get(start_key, s)
    end   = cfg.get(end_key,   e)
    step  = cfg.get(step_key,  st)
    n = max(1, int(round((end - start) / step)) + 1)
    return np.linspace(start, end, n)


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
        atr_position_sizing=cfg.get("ATR_POSITION_SIZING", False),
        risk_per_trade=cfg.get("RISK_PER_TRADE", 0.01),
    )


def _err(msg):
    logger.warning(f"[RSI] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
