# backtests/run_sentiment.py
"""
Sentiment-based backtest runner.
"""

import numpy as np
from utils.logging_utils import setup_logging
from utils import freq_utils
from utils.chunked_runner import simulate_and_rank
from data import vbt_data_loader as data_loader, data_cleaner
from sentiment import sentiment_data_loader, sentiment_analyzer
from signals import sentiment_signals

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
    Runs the Sentiment parameter sweep and returns the top-5 combinations.
    """
    try:
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sl_stop = _sl(backtest_config)
        tp_stop = _tp(backtest_config)

        # Build parameter ranges
        windows = _arange_int(
            strategy_config,
            "SENTIMENT_WINDOW_START", "SENTIMENT_WINDOW_END", "SENTIMENT_WINDOW_STEP",
            default=(1, 8, 1),
        )
        entry_thresholds = _linspace_float(
            strategy_config,
            "ENTRY_THRESHOLD_START", "ENTRY_THRESHOLD_END", "ENTRY_THRESHOLD_STEP",
            default=(0.05, 0.50, 0.05),
        )
        exit_thresholds = _linspace_float(
            strategy_config,
            "EXIT_THRESHOLD_START", "EXIT_THRESHOLD_END", "EXIT_THRESHOLD_STEP",
            default=(-0.50, -0.05, 0.05),
        )
        enable_shorting = backtest_config.get("ENABLE_SHORTING", False)

        if any(a.size == 0 for a in [windows, entry_thresholds, exit_thresholds]):
            return _err("One or more Sentiment parameter ranges is empty. Check settings.")

        # 1. Load price data
        logger.info(f"[Sentiment] Loading price data: {symbol} {interval} {start_date}->{end_date}")
        raw = data_loader.load_price_data_smart(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return _err(f"Could not load price data for '{symbol}'.")
        price_data = data_cleaner.clean_ohlcv_data(raw)
        if price_data is None or price_data.empty:
            return _err("Price data cleaning failed.")

        # 2. Load and score sentiment
        provider = strategy_config.get("PROVIDER", "alphavantage")
        logger.info(f"[Sentiment] Loading news from {provider} for {symbol}...")
        news_df = sentiment_data_loader.load_sentiment(
            ticker=symbol,
            start_date=start_date,
            end_date=end_date,
            provider=provider,
        )
        if news_df.empty:
            return _err(f"No news data found for '{symbol}' from {provider}.")

        # Map interval to pandas freq for aggregation
        agg_freq = freq_utils.interval_to_freq(interval)
        sentiment_series = sentiment_analyzer.aggregate_sentiment(news_df, freq=agg_freq)

        # 3. Generate signals
        n_combos = windows.size * entry_thresholds.size * exit_thresholds.size
        logger.info(f"[Sentiment] Generating signals (~{n_combos:,} combos)...")
        entries, exits, short_entries, short_exits = sentiment_signals.generate_sentiment_signals(
            close_prices_series=price_data["Close"],
            sentiment_series=sentiment_series,
            window=windows,
            entry_threshold=entry_thresholds,
            exit_threshold=exit_thresholds,
            enable_shorting=enable_shorting,
        )
        if entries is None or entries.empty:
            return _err("No entry signals generated.")

        # 4. Simulate + Rank
        logger.info("[Sentiment] Running simulation...")
        return simulate_and_rank(
            price_data=price_data,
            entries=entries,
            exits=exits,
            short_entries=short_entries if enable_shorting else None,
            short_exits=short_exits if enable_shorting else None,
            freq=freq,
            sim_kwargs=_sim_kwargs(backtest_config, sl_stop, tp_stop),
            strategy_tag="Sentiment",
            progress_callback=progress_callback,
        )

    except Exception as e:
        logger.exception(f"[Sentiment] Unexpected error: {e}")
        return _err(str(e))


# ---------------------------------------------------------------------------
# Helpers (same pattern as other runners)
# ---------------------------------------------------------------------------

def _arange_int(cfg, start_key, end_key, step_key, default):
    s, e, st = default
    return np.arange(cfg.get(start_key, s), cfg.get(end_key, e), cfg.get(step_key, st), dtype=int)


def _linspace_float(cfg, start_key, end_key, step_key, default):
    s, e, st = default
    start = cfg.get(start_key, s)
    end = cfg.get(end_key, e)
    step = cfg.get(step_key, st)
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
    logger.warning(f"[Sentiment] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
