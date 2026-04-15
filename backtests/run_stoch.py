# backtests/run_stoch.py
"""
Stochastic Crossover backtest runner.
Callable from the dashboard — same interface as run_ma, run_rsi, etc.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils
from utils.param_utils import top5_from_portfolio
from data import vbt_data_loader as data_loader, data_cleaner
from signals import stoch_crossover
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
    Runs the Stochastic Crossover parameter sweep and returns top-5 combinations.

    Returns a dict with keys:
      "top5"       — list of dicts (JSON-serializable), sorted by Sharpe desc.
      "error"      — None on success, or an error message string.
      "portfolio"  — live vectorbt Portfolio object (NOT JSON-safe).
      "price_data" — cleaned OHLCV DataFrame (NOT JSON-safe).
    """
    try:
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)
        enable_shorting = backtest_config.get("ENABLE_SHORTING", False)

        # Build parameter ranges
        k_start = strategy_config.get("STOCH_K_START", 5)
        k_end = strategy_config.get("STOCH_K_END", 21)
        k_step = strategy_config.get("STOCH_K_STEP", 1)
        k_windows = np.arange(k_start, k_end, k_step)

        d_start = strategy_config.get("STOCH_D_START", 3)
        d_end = strategy_config.get("STOCH_D_END", 10)
        d_step = strategy_config.get("STOCH_D_STEP", 1)
        d_windows = np.arange(d_start, d_end, d_step)

        if k_windows.size < 1 or d_windows.size < 1:
            return _err("Stochastic parameter ranges are empty.")

        n_combos = k_windows.size * d_windows.size
        logger.info(f"[STOCH] {n_combos} parameter combinations")

        # 1. Data
        logger.info(f"[STOCH] Loading data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load data for '{symbol}'. Check the ticker and date range.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Data cleaning failed.")

        # 2. Signals (Stochastic needs high, low, close)
        logger.info(f"[STOCH] Generating signals ({n_combos:,} combinations)...")
        entries, exits, short_entries, short_exits = stoch_crossover.generate_stoch_signals(
            price_data["High"],
            price_data["Low"],
            price_data["Close"],
            k_windows,
            d_windows,
            enable_shorting=enable_shorting,
        )
        if entries is None or entries.empty or not entries.any().any():
            return _err("No entry signals generated. Try a wider date range or different parameters.")

        # 3. Simulate
        logger.info("[STOCH] Running simulation...")
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
        logger.info("[STOCH] Ranking combinations...")
        top5 = top5_from_portfolio(portfolio, n=5)
        return {"top5": top5, "error": None, "portfolio": portfolio, "price_data": price_data}

    except Exception as e:
        logger.exception(f"[STOCH] Unexpected error: {e}")
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
    logger.warning(f"[STOCH] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
