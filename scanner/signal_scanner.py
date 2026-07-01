# scanner/signal_scanner.py
"""
Signal scanner — checks whether saved backtest parameters are currently
generating a BUY, SELL, or active-position signal.

Usage:
    python -m scanner.signal_scanner

Configure what to scan in scanner/scan_config.py.
"""

import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

# Load .env so ALPACA_API_KEY is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from data.vbt_data_loader import load_price_data_smart
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

# ---------------------------------------------------------------------------
# Bars-per-trading-day for each supported interval
# ---------------------------------------------------------------------------
_BARS_PER_DAY = {
    "1D": 1, "1d": 1,
    "1h": 7, "60m": 7,
    "30m": 13,
    "15m": 26,
    "5m":  78,
    "2m":  195,
    "1m":  390,
}


# ---------------------------------------------------------------------------
# Indicator helpers (pure pandas — no vectorbt sweep needed for single params)
# ---------------------------------------------------------------------------

def _rsi(close: pd.Series, window: int) -> pd.Series:
    """Wilder-smoothed RSI matching vectorbt's default implementation."""
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


# ---------------------------------------------------------------------------
# Per-strategy signal checkers
# Return dict with keys: signal ("BUY"/"SELL"/"IN_TRADE"/"OUT"), plus indicator values
# ---------------------------------------------------------------------------

def _check_ma(close: pd.Series, params: dict) -> dict:
    fast_w = params["fast_window"]
    slow_w = params["slow_window"]

    fast = close.rolling(fast_w).mean()
    slow = close.rolling(slow_w).mean()

    # Need at least 2 valid (non-NaN) bars for crossover detection
    valid = fast.dropna()
    if len(valid) < 2:
        return {"signal": "INSUFFICIENT_DATA", "fast_ma": None, "slow_ma": None}

    prev_fast, curr_fast = fast.iloc[-2], fast.iloc[-1]
    prev_slow, curr_slow = slow.iloc[-2], slow.iloc[-1]

    if pd.isna(prev_fast) or pd.isna(prev_slow):
        return {"signal": "INSUFFICIENT_DATA", "fast_ma": None, "slow_ma": None}

    crossed_above = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
    crossed_below = (prev_fast >= prev_slow) and (curr_fast < curr_slow)

    if crossed_above:
        signal = "BUY"
    elif crossed_below:
        signal = "SELL"
    elif curr_fast > curr_slow:
        signal = "IN_TRADE"   # fast still above slow — position open, no new signal
    else:
        signal = "OUT"        # fast below slow — no position

    return {
        "signal":   signal,
        "fast_ma":  round(curr_fast, 4),
        "slow_ma":  round(curr_slow, 4),
    }


def _check_rsi(close: pd.Series, params: dict) -> dict:
    window          = params["rsi_window"]
    entry_threshold = params["entry_threshold"]
    exit_threshold  = params["exit_threshold"]

    rsi = _rsi(close, window)
    valid = rsi.dropna()
    if len(valid) < 2:
        return {"signal": "INSUFFICIENT_DATA", "rsi": None}

    prev_rsi = rsi.iloc[-2]
    curr_rsi = rsi.iloc[-1]

    if pd.isna(prev_rsi):
        return {"signal": "INSUFFICIENT_DATA", "rsi": None}

    crossed_above_entry = (prev_rsi < entry_threshold) and (curr_rsi >= entry_threshold)
    crossed_below_exit  = (prev_rsi > exit_threshold)  and (curr_rsi <= exit_threshold)

    if crossed_above_entry:
        signal = "BUY"
    elif crossed_below_exit:
        signal = "SELL"
    elif entry_threshold <= curr_rsi <= exit_threshold:
        signal = "IN_TRADE"
    else:
        signal = "OUT"

    return {
        "signal":          signal,
        "rsi":             round(curr_rsi, 2),
        "entry_threshold": entry_threshold,
        "exit_threshold":  exit_threshold,
    }


def _check_macd(close: pd.Series, params: dict) -> dict:
    fast_w   = params["fast_window"]
    slow_w   = params["slow_window"]
    signal_w = params["signal_window"]

    macd_line   = _ema(close, fast_w) - _ema(close, slow_w)
    signal_line = _ema(macd_line, signal_w)

    valid = signal_line.dropna()
    if len(valid) < 2:
        return {"signal": "INSUFFICIENT_DATA", "macd": None, "signal_line": None}

    prev_macd, curr_macd     = macd_line.iloc[-2],   macd_line.iloc[-1]
    prev_sig,  curr_sig      = signal_line.iloc[-2], signal_line.iloc[-1]

    if pd.isna(prev_macd) or pd.isna(prev_sig):
        return {"signal": "INSUFFICIENT_DATA", "macd": None, "signal_line": None}

    crossed_above = (prev_macd <= prev_sig) and (curr_macd > curr_sig)
    crossed_below = (prev_macd >= prev_sig) and (curr_macd < curr_sig)

    if crossed_above:
        signal = "BUY"
    elif crossed_below:
        signal = "SELL"
    elif curr_macd > curr_sig:
        signal = "IN_TRADE"
    else:
        signal = "OUT"

    return {
        "signal":      signal,
        "macd":        round(curr_macd, 4),
        "signal_line": round(curr_sig, 4),
    }


def _check_volume(close: pd.Series, volume: pd.Series, params: dict) -> dict:
    vol_window   = params["volume_window"]
    multiplier   = params["volume_multiplier"]
    exit_ma_w    = params["exit_ma_window"]
    confirm_up   = params.get("confirm_price_increase", False)

    avg_vol  = volume.rolling(vol_window).mean()
    exit_ma  = close.rolling(exit_ma_w).mean()

    if pd.isna(avg_vol.iloc[-1]) or pd.isna(exit_ma.iloc[-1]):
        return {"signal": "INSUFFICIENT_DATA", "vol_ratio": None, "exit_ma": None}

    curr_vol    = volume.iloc[-1]
    curr_avg    = avg_vol.iloc[-1]
    vol_ratio   = curr_vol / curr_avg if curr_avg > 0 else 0.0

    vol_breakout = curr_vol > multiplier * curr_avg
    price_up     = close.iloc[-1] > close.iloc[-2] if confirm_up else True
    entry        = vol_breakout and price_up
    exit_sig     = close.iloc[-1] < exit_ma.iloc[-1]

    if entry:
        signal = "BUY"
    elif exit_sig:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "signal":    signal,
        "vol_ratio": round(vol_ratio, 2),
        "exit_ma":   round(exit_ma.iloc[-1], 4),
    }


def _check_bbands(close: pd.Series, params: dict) -> dict:
    window = params["bb_window"]
    alpha  = params["bb_alpha"]

    middle = close.rolling(window).mean()
    std    = close.rolling(window).std(ddof=0)   # ddof=0 to match vbt.BBANDS
    upper  = middle + alpha * std
    lower  = middle - alpha * std

    valid = middle.dropna()
    if len(valid) < 2:
        return {"signal": "INSUFFICIENT_DATA", "upper": None, "middle": None, "lower": None}

    prev_close, curr_close = close.iloc[-2], close.iloc[-1]
    prev_upper, curr_upper = upper.iloc[-2], upper.iloc[-1]
    prev_mid,   curr_mid   = middle.iloc[-2], middle.iloc[-1]

    if pd.isna(prev_upper) or pd.isna(prev_mid):
        return {"signal": "INSUFFICIENT_DATA", "upper": None, "middle": None, "lower": None}

    # Backtest logic: enter long when price breaks above the upper band,
    # exit when price falls back below the middle band.
    crossed_above_upper = (prev_close <= prev_upper) and (curr_close > curr_upper)
    crossed_below_mid   = (prev_close >= prev_mid)   and (curr_close < curr_mid)

    if crossed_above_upper:
        signal = "BUY"
    elif crossed_below_mid:
        signal = "SELL"
    elif curr_close > curr_mid:
        signal = "IN_TRADE"   # price still above the middle band — long open
    else:
        signal = "OUT"

    return {
        "signal": signal,
        "upper":  round(curr_upper, 4),
        "middle": round(curr_mid, 4),
        "lower":  round(lower.iloc[-1], 4),
    }


def _check_stoch(high: pd.Series, low: pd.Series, close: pd.Series, params: dict) -> dict:
    k_window   = params["k_window"]
    d_window   = params["d_window"]
    oversold   = params["oversold"]
    overbought = params["overbought"]

    lowest_low   = low.rolling(k_window).min()
    highest_high = high.rolling(k_window).max()
    rng          = (highest_high - lowest_low).replace(0, np.nan)
    percent_k    = 100 * (close - lowest_low) / rng
    percent_d    = percent_k.rolling(d_window).mean()

    valid = percent_d.dropna()
    if len(valid) < 2:
        return {"signal": "INSUFFICIENT_DATA", "percent_k": None, "percent_d": None}

    prev_k, curr_k = percent_k.iloc[-2], percent_k.iloc[-1]
    prev_d, curr_d = percent_d.iloc[-2], percent_d.iloc[-1]

    if pd.isna(prev_k) or pd.isna(prev_d):
        return {"signal": "INSUFFICIENT_DATA", "percent_k": None, "percent_d": None}

    crossed_above = (prev_k <= prev_d) and (curr_k > curr_d)
    crossed_below = (prev_k >= prev_d) and (curr_k < curr_d)

    # Backtest logic: long entry on %K crossing above %D while oversold;
    # long exit on %K crossing below %D while overbought.
    if crossed_above and curr_k < oversold:
        signal = "BUY"
    elif crossed_below and curr_k > overbought:
        signal = "SELL"
    elif curr_k > curr_d:
        signal = "IN_TRADE"
    else:
        signal = "OUT"

    return {
        "signal":    signal,
        "percent_k": round(curr_k, 2),
        "percent_d": round(curr_d, 2),
    }


# ---------------------------------------------------------------------------
# Core scan function
# ---------------------------------------------------------------------------

def scan_one(scan: dict) -> dict:
    """
    Runs a single scan entry and returns a result dict.

    Args:
        scan: Dict with keys: strategy, symbol, interval, params.

    Returns:
        Dict with keys: symbol, strategy, interval, params, signal, price,
                        indicator_values, error.
    """
    strategy = scan["strategy"].lower()
    symbol   = scan["symbol"].upper()
    interval = scan["interval"]
    params   = scan["params"]

    result = {
        "symbol":           symbol,
        "strategy":         strategy,
        "interval":         interval,
        "params":           params,
        "signal":           None,
        "price":            None,
        "indicator_values": {},
        "error":            None,
    }

    # --- Compute how far back to look ---
    if strategy == "ma":
        min_bars = params["slow_window"] * 3
    elif strategy == "rsi":
        min_bars = params["rsi_window"] * 3
    elif strategy == "macd":
        min_bars = params["slow_window"] * 3
    elif strategy == "volume":
        min_bars = max(params["volume_window"], params["exit_ma_window"]) * 3
    elif strategy == "bbands":
        min_bars = params["bb_window"] * 3
    elif strategy == "stoch":
        min_bars = (params["k_window"] + params["d_window"]) * 3
    else:
        result["error"] = f"Unknown strategy '{strategy}'"
        return result

    bars_per_day    = _BARS_PER_DAY.get(interval, 1)
    trading_days    = max(min_bars / bars_per_day, 1)
    calendar_days   = int(trading_days * 1.5) + 10  # buffer for weekends/holidays
    from utils.date_utils import generate_date_range
    start_date, end_date = generate_date_range(days_back=calendar_days)

    # --- Download data ---
    logger.info(f"[scanner] {symbol} {strategy} — fetching {interval} data ({start_date} → {end_date})")
    df = load_price_data_smart(symbol, start_date, end_date, interval)

    if df is None or df.empty:
        result["error"] = "No data returned — check ticker/interval/date range."
        return result

    if len(df) < 3:
        result["error"] = f"Not enough bars ({len(df)}) to compute indicator."
        return result

    close  = df["Close"]
    result["price"] = round(float(close.iloc[-1]), 4)

    # --- Compute signal ---
    if strategy == "ma":
        info = _check_ma(close, params)
    elif strategy == "rsi":
        info = _check_rsi(close, params)
    elif strategy == "macd":
        info = _check_macd(close, params)
    elif strategy == "volume":
        if "Volume" not in df.columns:
            result["error"] = "Volume column missing from data."
            return result
        info = _check_volume(close, df["Volume"], params)
    elif strategy == "bbands":
        info = _check_bbands(close, params)
    elif strategy == "stoch":
        missing = [c for c in ("High", "Low") if c not in df.columns]
        if missing:
            result["error"] = f"{', '.join(missing)} column(s) missing from data (required for Stochastic)."
            return result
        info = _check_stoch(df["High"], df["Low"], close, params)

    result["signal"]           = info.pop("signal")
    result["indicator_values"] = info
    return result


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

_SIGNAL_LABELS = {
    "BUY":               "BUY  ",
    "SELL":              "SELL ",
    "IN_TRADE":          "HOLD ",   # position open, no new crossover
    "OUT":               "OUT  ",   # no position
    "HOLD":              "HOLD ",
    "INSUFFICIENT_DATA": "DATA?",
}

def _format_result(r: dict) -> str:
    label  = _SIGNAL_LABELS.get(r["signal"], r["signal"])
    param_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
    ind_str   = "  ".join(f"{k}={v}" for k, v in r["indicator_values"].items())

    line = (
        f"[{label}]  {r['symbol']:<6}  {r['strategy'].upper():<6}  "
        f"({param_str})  |  price={r['price']}  {ind_str}"
    )
    if r.get("error"):
        line += f"  ERROR: {r['error']}"
    return line


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_all_scans(scans: list) -> list[dict]:
    results = []
    for scan in scans:
        try:
            results.append(scan_one(scan))
        except Exception as e:
            logger.exception(f"[scanner] Unhandled error scanning {scan}: {e}")
            results.append({**scan, "signal": "ERROR", "error": str(e)})
    return results


if __name__ == "__main__":
    from scanner.scan_config import SCANS

    if not SCANS:
        print("No scans configured. Edit scanner/scan_config.py and add entries to SCANS.")
        sys.exit(0)

    from datetime import datetime
    print(f"\n=== Signal Scanner — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    results = run_all_scans(SCANS)
    for r in results:
        print(_format_result(r))

    print()
