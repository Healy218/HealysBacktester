"""On-disk store of streamed 1-minute stock bars, read back as the same 15m
RTH frame the REST loader returns (tz-naive UTC index = bar START, columns
Open/High/Low/Close/Volume, floats).

Layout: ``<root>/1m/<SYMBOL>/<YYYY-MM-DD>.parquet`` — one file per symbol per
session, rewritten atomically on every append (a day is ≤ 390 rows, so the
rewrite is cheap and readers never see a torn file).

Aggregation 1m → 15m follows Alpaca's bar convention: a 15m bar stamped
13:30 covers [13:30, 13:45); Open = first 1m open, High = max, Low = min,
Close = last 1m close, Volume = sum. Only COMPLETE 15m buckets are returned
(all of the bucket's 1m bars must be on or before ``now - 1min``... in
practice: the bucket's end must be ≤ now), so the scanner's own
``closed_bars`` trim stays the single source of truth for "closed".
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
                 days: Optional[Iterable[str]] = None) -> pd.DataFrame:
        """Complete RTH 15m bars aggregated from the stored 1m bars, in the REST
        loader's exact shape."""
        m1 = self.read_1m(symbol, days)
        if m1.empty:
            return pd.DataFrame(columns=COLS)
        return aggregate_15m(m1, now=now)

    def coverage(self, symbol: str) -> dict:
        m1 = self.read_1m(symbol)
        if m1.empty:
            return {"rows": 0, "first": None, "last": None}
        return {"rows": int(len(m1)), "first": str(m1.index[0]), "last": str(m1.index[-1])}


def aggregate_15m(m1: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """1m OHLCV (tz-naive UTC index) → complete 15m RTH bars."""
    if m1.empty:
        return pd.DataFrame(columns=COLS)
    m1 = filter_rth(m1)
    if m1.empty:
        return pd.DataFrame(columns=COLS)
    g = m1.groupby(m1.index.floor("15min"))
    out = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(),
                        "Low": g["Low"].min(), "Close": g["Close"].last(),
                        "Volume": g["Volume"].sum()})
    out.index.name = "timestamp"
    if now is not None:
        cutoff = _to_naive_utc(now)
        out = out[out.index + _BAR15 <= cutoff]
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
