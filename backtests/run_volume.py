# backtests/run_volume.py
"""
Volume Breakout backtest runner.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils
from utils.param_utils import top5_from_portfolio
from data import data_loader, data_cleaner
from signals import volume_breakout
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
    Runs the Volume Breakout parameter sweep and returns the top-5 combinations.
    See run_ma.py for return dict structure.
    """
    try:
        freq    = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)

        vol_windows = np.arange(
            strategy_config.get("VOLUME_WINDOW_START", 30),
            strategy_config.get("VOLUME_WINDOW_END",   60),
            strategy_config.get("VOLUME_WINDOW_STEP",  2),
            dtype=int,
        )
        vol_mults = _linspace(
            strategy_config,
            "VOLUME_MULTIPLIER_START", "VOLUME_MULTIPLIER_END", "VOLUME_MULTIPLIER_STEP",
            default=(1.5, 2.0, 0.1),
        )
        exit_ma_windows = np.arange(
            strategy_config.get("EXIT_MA_WINDOW_START", 45),
            strategy_config.get("EXIT_MA_WINDOW_END",   90),
            strategy_config.get("EXIT_MA_WINDOW_STEP",  1),
            dtype=int,
        )
        confirm_price_increase = strategy_config.get("CONFIRM_PRICE_INCREASE", False)

        if any(a.size == 0 for a in [vol_windows, vol_mults, exit_ma_windows]):
            return _err("One or more Volume parameter ranges is empty. Check settings.")

        # 1. Data
        logger.info(f"[VOL] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'.")
        if "Volume" not in raw.columns:
            return _err("Volume column missing from data. Volume Breakout requires volume data.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        # 2. Signals
        n_combos = vol_windows.size * vol_mults.size * exit_ma_windows.size
        logger.info(f"[VOL] Generating signals ({n_combos:,} combos)…")
        entries, exits, _, _ = volume_breakout.generate_volume_signals(
            ohlcv_df=price_data,
            volume_window_range=vol_windows,
            volume_multiplier_range=vol_mults,
            exit_ma_window_range=exit_ma_windows,
            confirm_price_increase=confirm_price_increase,
        )
        if entries is None or entries.empty:
            return _err("No entry signals generated.")

        # 3. Simulate
        logger.info("[VOL] Running simulation…")
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=None,
            short_exits_series=None,
            frequency=freq,
            **_sim_kwargs(backtest_config, sl_stop, tp_stop),
        )
        if portfolio is None:
            return _err("Simulation returned no portfolio.")

        # 4. Rank
        logger.info("[VOL] Ranking combinations…")
        top5 = top5_from_portfolio(portfolio, n=5)
        return {"top5": top5, "error": None, "portfolio": portfolio, "price_data": price_data}

    except Exception as e:
        logger.exception(f"[VOL] Unexpected error: {e}")
        return _err(str(e))


def _linspace(cfg, sk, ek, stk, default):
    s, e, st = default
    start = cfg.get(sk, s)
    end   = cfg.get(ek, e)
    step  = cfg.get(stk, st)
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
    )


def _err(msg):
    logger.warning(f"[VOL] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
