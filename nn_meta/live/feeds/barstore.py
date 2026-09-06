"""On-disk store of streamed 1-minute stock bars, read back as the same 15m
RTH frame the REST loader returns (tz-naive UTC index = bar START, columns
Open/High/Low/Close/Volume, floats).

Layout: ``<root>/1m/<SYMBOL>/<YYYY-MM-DD>.parquet`` — one file per symbol per
session, rewritten atomically on every append (a day is ≤ 390 rows, so the
rewrite is cheap and readers never see a torn file).

Aggregation 1m → 15m follows Alpaca's bar convention: a 15m bar stamped
13:30 covers [13:30, 13:45); Open = first 1m open, High = max, Low = min,
Close = last 1m close, Volume = sum. Only COMPLETE 15m buckets are returned
(the bucket's end must be ≤ now and all 15 distinct minute starts must
be present). An elapsed bucket with missing or malformed minutes raises
ValueError so the live loader can fall back to REST. This deliberately
includes sparse no-trade minutes: the stream never fabricates missing bars.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from nn_meta import config
from nn_meta.download_data import filter_rth

ROOT = config.ROOT / "live" / "feeds" / "data"
COLS = ["Open", "High", "Low", "Close", "Volume"]
_BAR15 = pd.Timedelta(minutes=15)


def _day_path(root: Path, symbol: str, day: str) -> Path:
    return root / "1m" / symbol.upper() / f"{day}.parquet"


def _to_naive_utc(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t


class BarStore:
    def __init__(self, root: Path | str = ROOT):
        self.root = Path(root)

    # ── write ────────────────────────────────────────────────────────────────
    def append_1m(self, symbol: str, bars: Iterable[dict]) -> int:
        """Append 1m bars ({timestamp, open, high, low, close, volume}) for one
        symbol. Idempotent on timestamp (last write wins). Returns rows kept."""
        rows = []
        for b in bars:
            ts = _to_naive_utc(b["timestamp"])
            rows.append({"timestamp": ts, "Open": float(b["open"]), "High": float(b["high"]),
                         "Low": float(b["low"]), "Close": float(b["close"]),
                         "Volume": float(b["volume"])})
        if not rows:
            return 0
        new = pd.DataFrame(rows).set_index("timestamp")
        total = 0
        for day, chunk in new.groupby(new.index.strftime("%Y-%m-%d")):
            path = _day_path(self.root, symbol, day)
            path.parent.mkdir(parents=True, exist_ok=True)
            old = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=COLS)
            merged = pd.concat([old, chunk]) if not old.empty else chunk
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            tmp = path.with_suffix(f".tmp.{os.getpid()}")
            merged.to_parquet(tmp)
            os.replace(tmp, path)
            total += len(merged)
        return total

    # ── read ─────────────────────────────────────────────────────────────────
    def read_1m(self, symbol: str, days: Optional[Iterable[str]] = None) -> pd.DataFrame:
        d = self.root / "1m" / symbol.upper()
        if not d.exists():
            return pd.DataFrame(columns=COLS)
        files = sorted(d.glob("*.parquet"))
        if days is not None:
            want = set(days)
            files = [f for f in files if f.stem in want]
        if not files:
            return pd.DataFrame(columns=COLS)
        out = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
        out.index.name = "timestamp"
        return out[COLS].astype(float)

    def read_15m(self, symbol: str, now: Optional[datetime] = None,
                 days: Optional[Iterable[str]] = None, *, calendar=None) -> pd.DataFrame:
        """Complete RTH 15m bars aggregated from the stored 1m bars, in the REST
        loader's exact shape."""
        m1 = self.read_1m(symbol, days)
        if m1.empty:
            return pd.DataFrame(columns=COLS)
        return aggregate_15m(m1, now=now, calendar=calendar)

    def coverage(self, symbol: str) -> dict:
        m1 = self.read_1m(symbol)
        if m1.empty:
            return {"rows": 0, "first": None, "last": None}
        return {"rows": int(len(m1)), "first": str(m1.index[0]), "last": str(m1.index[-1])}


def aggregate_15m(m1: pd.DataFrame, now: Optional[datetime] = None, *, calendar=None) -> pd.DataFrame:
    """1m OHLCV (tz-naive UTC index) → complete 15m RTH bars.

    Without ``now``, the last observed minute's end is the cutoff. Forming
    buckets are discarded before validation. Entirely absent buckets require
    the caller's session coverage check, since they leave no stream rows.
    """
    if m1.empty:
        return pd.DataFrame(columns=COLS)
    m1 = calendar.filter(m1, bar_minutes=1) if calendar is not None else filter_rth(m1)
    if m1.empty:
        return pd.DataFrame(columns=COLS)
    cutoff = (_to_naive_utc(now) if now is not None
              else m1.index.max().floor("min") + pd.Timedelta(minutes=1))
    m1 = m1[m1.index.floor("15min") + _BAR15 <= cutoff].sort_index()
    if m1.empty:
        return pd.DataFrame(columns=COLS)
    g = m1.groupby(m1.index.floor("15min"))
    for bucket, minutes in g:
        expected = pd.date_range(bucket, periods=15, freq="1min")
        if not minutes.index.equals(expected):
            raise ValueError(f"Incomplete or malformed streamed 15m bucket {bucket}: "
                             "expected 15 distinct minute-aligned bars")
    out = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(),
                        "Low": g["Low"].min(), "Close": g["Close"].last(),
                        "Volume": g["Volume"].sum()})
    out.index.name = "timestamp"
    return out.astype(float)


def write_heartbeat(path: Path | str, **fields) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}))
    os.replace(tmp, p)


def read_heartbeat(path: Path | str) -> Optional[dict]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None
