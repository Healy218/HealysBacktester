"""Latest NBBO per option contract from the OPRA quote stream.

One small JSON file (atomic replace) keyed by OCC symbol:
  {"SPY260918C00650000": {"bid": 1.23, "ask": 1.27, "bid_size": 10, "ask_size": 8,
                          "ts": "2026-09-08T14:30:01.123456Z"}, ...}
Readers (alert formatter, paper seat) take the whole map; writers hold it in
memory and flush on a timer. Contracts not in the map are simply unknown —
callers fall back to the Massive REST snapshot.
"""
from __future__ import annotations
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd

from nn_meta import config

ROOT = config.ROOT / "live" / "feeds" / "data"
PATH = ROOT / "option_quotes.json"
HEARTBEAT = ROOT / "option_stream.heartbeat.json"


def _to_occ(symbol: str) -> str:
    return symbol.upper().removeprefix("O:")


def _timestamp(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("quote timestamps must be timezone-aware")
    return stamp.tz_convert("UTC")


def _valid_quote(q: dict) -> bool:
    if not isinstance(q, dict):
        return False
    try:
        values = [q[k] for k in ("bid", "ask", "bid_size", "ask_size")]
        if any(isinstance(v, bool) or not math.isfinite(float(v)) for v in values):
            return False
        bid, ask, bid_size, ask_size = map(float, values)
        return 0 < bid <= ask and bid_size > 0 and ask_size > 0
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _quote_number(value):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


class QuoteStore:
    def __init__(self, path: Path | str = PATH):
        self.path = Path(path)
        self._map: dict[str, dict] = {}

    def update(self, symbol: str, *, bid: float, ask: float, bid_size: float = 0,
               ask_size: float = 0, ts=None) -> None:
        occ = _to_occ(symbol)
        stamp = _timestamp(ts if ts is not None else datetime.now(timezone.utc))
        previous = self._map.get(occ)
        if previous is not None and stamp < _timestamp(previous["ts"]):
            return
        # Keep cancellations/crossed quotes as the latest observation so a
        # reader refuses them instead of silently using an older valid quote.
        self._map[occ] = {
            "bid": _quote_number(bid), "ask": _quote_number(ask),
            "bid_size": _quote_number(bid_size), "ask_size": _quote_number(ask_size),
            "ts": stamp.isoformat()}

    def flush(self) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(self._map, allow_nan=False))
        os.replace(tmp, self.path)
        return len(self._map)

    @classmethod
    def load(cls, path: Path | str = PATH) -> dict[str, dict]:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            value = json.loads(p.read_text())
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def get(symbol: str, path: Path | str = PATH, max_age_s: Optional[float] = None,
            *, now=None) -> Optional[dict]:
        q = QuoteStore.load(path).get(_to_occ(symbol))
        if q is None or not _valid_quote(q):
            return None
        try:
            current = _timestamp(now if now is not None else datetime.now(timezone.utc))
            quoted = _timestamp(q["ts"])
            age_ns = current.value - quoted.value
            if age_ns < 0:
                return None
            if max_age_s is not None:
                if not math.isfinite(float(max_age_s)) or max_age_s < 0:
                    return None
                if age_ns > max_age_s * 1_000_000_000:
                    return None
        except (TypeError, ValueError, KeyError, OverflowError):
            return None
        return q


def spread_bps(q: dict) -> Optional[float]:
    try:
        bid, ask = float(q["bid"]), float(q["ask"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(bid) or not math.isfinite(ask) or not 0 < bid <= ask:
        return None
    return (ask - bid) / ((bid + ask) / 2) * 1e4
