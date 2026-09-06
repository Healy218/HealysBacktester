# nn_meta/download_data.py
"""Pull 15-minute underlying bars for all universe names into one parquet.

Alpaca serves 15m stock history (paginated) — this avoids Massive's ~5/min
stock-aggregates tier entirely. Bars are filtered to REGULAR TRADING HOURS
(09:30–16:00 ET) so the underlying timeline matches when options actually
print, then stored tz-naive UTC — the same convention as Massive option bars,
which is what options/execution.py compares against.

Run:  python -m nn_meta.download_data
"""
import pandas as pd
import numbers

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from data import vbt_data_loader
from nn_meta import config

_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Keep 09:30 <= t < 16:00 America/New_York; index in/out is tz-naive UTC.

    DST-correct: conversion goes through the exchange timezone, so a January
    09:30 ET bar (14:30 UTC) and a June one (13:30 UTC) both survive.
    """
    if df.empty:
        return df
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    et = idx.tz_convert("America/New_York")
    mask = (et.hour * 60 + et.minute >= 9 * 60 + 30) & (et.hour < 16)
    out = df[mask].copy()
    out.index = idx[mask].tz_localize(None)
    out.index.name = "timestamp"
    return out


def _load_chunked(sym: str, start: str, end: str, months: int = 4) -> pd.DataFrame:
    """Fetch in date chunks: the Alpaca loader returns a single 10k-bar page,
    which truncates a multi-year 15m request (~64 extended-hours bars/day ≈
    5 months per page). 4-month chunks stay well under the cap.

    The public date window is inclusive. Vendor end timestamps denote
    midnight, so adjacent requests must meet at the same boundary; subtracting
    one day before each request drops the entire last session of the chunk.
    Clip each response to [lo, hi) in case the provider includes its endpoint.
    """
    if isinstance(months, bool) or not isinstance(months, numbers.Integral) or months < 1:
        raise ValueError("months must be a positive integer")
    frames = []
    lo = pd.Timestamp(start).normalize()
    hard_end = pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
    if lo >= hard_end:
        raise ValueError("start must not follow end")
    while lo < hard_end:
        hi = min(lo + pd.DateOffset(months=int(months)), hard_end)
        chunk = vbt_data_loader.load_price_data_smart(
            sym, lo.date().isoformat(), hi.date().isoformat(), config.INTERVAL)
        if chunk is not None and not chunk.empty:
            idx = pd.DatetimeIndex(chunk.index)
            compare = idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx
            frames.append(chunk[(compare >= lo) & (compare < hi)])
        lo = hi
    if not frames:
        return pd.DataFrame(columns=_OHLCV)
    out = pd.concat(frames)
    return out[~out.index.duplicated(keep="first")].sort_index()


def main() -> None:
    config.ensure_dirs()
    frames = []
    print(f"downloading 15m bars for {len(config.UNDERLYINGS)} names "
          f"({config.HISTORY_START} → {config.WINDOW_END}, RTH only)")
    for sym in config.UNDERLYINGS:
        # fetch under vendor symbology (BRKB→BRK.B) or the current exchange
        # ticker for renamed listings; rows stay keyed on sym
        fetch_sym = config.FETCH_ALIASES.get(sym) \
            or config.TICKER_ALIASES.get(sym, sym)
        raw = _load_chunked(fetch_sym, config.HISTORY_START, config.WINDOW_END)
        if raw is None or raw.empty:
            print(f"  {sym:6s}: NO DATA")
            continue
        df = filter_rth(raw[_OHLCV])
        days = df.index.normalize().nunique()
        print(f"  {sym:6s}: {len(df):7d} rows | {days:4d} days | "
              f"{df.index[0].date()} → {df.index[-1].date()} "
              f"({len(df) / max(days, 1):.1f} bars/day)")
        df = df.reset_index()
        df.insert(0, "symbol", sym)
        frames.append(df)

    if not frames:
        raise SystemExit("no data downloaded for any symbol")
    panel = pd.concat(frames, ignore_index=True)
    panel.to_parquet(config.UNDERLYING_15M_PARQUET, index=False)
    mb = config.UNDERLYING_15M_PARQUET.stat().st_size / 1024 ** 2
    print(f"\nwrote {config.UNDERLYING_15M_PARQUET} "
          f"({len(panel):,} rows, {panel['symbol'].nunique()} symbols, {mb:.1f} MB)")


if __name__ == "__main__":
    main()
