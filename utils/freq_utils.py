# utils/freq_utils.py
"""
Utilities for converting Yahoo Finance interval strings to vectorbt frequency strings.

vectorbt uses pandas offset aliases for its `freq` parameter. Getting this wrong
causes all annualized metrics (Sharpe, CAGR, period calculations) to be massively
incorrect — e.g., '5m' data with freq='D' shows 5000-day periods instead of 17 days.

Reference: https://pandas.pydata.org/docs/user_guide/timeseries.html#offset-aliases
"""

# Maps Yahoo Finance interval strings → pandas/vectorbt offset aliases.
# Pandas deprecated single-letter minute aliases ('T', 'min') in 2.x — use 'min' suffix.
_INTERVAL_TO_FREQ = {
    '1m':  '1min',
    '2m':  '2min',
    '5m':  '5min',
    '15m': '15min',
    '30m': '30min',
    '60m': '60min',
    '90m': '90min',
    '1h':  '1h',
    '1d':  'D',
    '1D':  'D',
    '5d':  '5D',
    '1wk': 'W',
    '1W':  'W',
    '1mo': 'ME',   # Month End
    '3mo': 'QE',   # Quarter End
}


def interval_to_freq(interval: str) -> str:
    """
    Converts a Yahoo Finance interval string to the correct vectorbt/pandas freq string.

    Args:
        interval: Yahoo Finance interval string (e.g., '5m', '1h', '1D').

    Returns:
        Pandas offset alias suitable for vectorbt's freq parameter.

    Raises:
        ValueError: If the interval string is not recognized.
    """
    freq = _INTERVAL_TO_FREQ.get(interval)
    if freq is None:
        raise ValueError(
            f"Unknown interval '{interval}'. "
            f"Supported values: {list(_INTERVAL_TO_FREQ.keys())}"
        )
    return freq


def resolve_freq(config_freq, interval: str) -> str:
    """
    Resolves the vectorbt frequency string to use.

    If config_freq is None or empty, auto-detects from the interval string.
    If config_freq is explicitly set, uses that value (with a deprecation warning
    for the old 'T' alias).

    Args:
        config_freq: Value of DEFAULT_FREQ from BACKTEST_CONFIG (or None).
        interval: Data interval string from DATA_CONFIG (e.g., '5m', '1D').

    Returns:
        Resolved pandas offset alias string.
    """
    if not config_freq:
        return interval_to_freq(interval)

    # Warn about deprecated single-char pandas aliases
    if config_freq in ('T', 'min'):
        import warnings
        warnings.warn(
            f"Frequency alias '{config_freq}' is deprecated in pandas 2.x. "
            f"Use '1min' or '5min' etc. instead. Auto-detecting from interval '{interval}'.",
            DeprecationWarning, stacklevel=2
        )
        return interval_to_freq(interval)

    return config_freq
