# backtests/run_volume.py
"""
Volume Breakout backtest runner.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils, runner_utils
from utils.chunked_runner import simulate_and_rank
from data import vbt_data_loader as data_loader, data_cleaner
from signals import volume_breakout

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

        # 3. Simulate + Rank (chunked for large sweeps)
        logger.info("[VOL] Running simulation…")
        return simulate_and_rank(
            price_data=price_data,
            entries=entries,
            exits=exits,
            short_entries=None,
            short_exits=None,
            freq=freq,
            sim_kwargs=_sim_kwargs(backtest_config, sl_stop, tp_stop),
            strategy_tag="VOL",
            progress_callback=progress_callback,
        )

    except Exception as e:
        logger.exception(f"[VOL] Unexpected error: {e}")
        return _err(str(e))


_linspace = runner_utils.linspace
_sl = runner_utils.sl_stop
_tp = runner_utils.tp_stop


def _sim_kwargs(cfg, sl_stop=None, tp_stop=None):
    return runner_utils.sim_kwargs(cfg, sl_stop, tp_stop)


def _err(msg):
    return runner_utils.err(msg, "VOL", logger)
