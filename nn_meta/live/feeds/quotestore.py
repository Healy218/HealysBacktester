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
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from nn_meta import config

ROOT = config.ROOT / "live" / "feeds" / "data"
PATH = ROOT / "option_quotes.json"
HEARTBEAT = ROOT / "option_stream.heartbeat.json"


def _to_occ(symbol: str) -> str:
    return symbol.removeprefix("O:").upper()


class QuoteStore:
    def __init__(self, path: Path | str = PATH):
        self.path = Path(path)
        self._map: dict[str, dict] = {}

    def update(self, symbol: str, *, bid: float, ask: float, bid_size: float = 0,
               ask_size: float = 0, ts=None) -> None:
        self._map[_to_occ(symbol)] = {
            "bid": float(bid), "ask": float(ask), "bid_size": float(bid_size),
            "ask_size": float(ask_size),
            "ts": (ts.isoformat() if hasattr(ts, "isoformat") else str(ts)) if ts is not None
                  else datetime.now(timezone.utc).isoformat()}

    def flush(self) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(self._map))
        os.replace(tmp, self.path)
        return len(self._map)

    @classmethod
    def load(cls, path: Path | str = PATH) -> dict[str, dict]:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}

    @staticmethod
    def get(symbol: str, path: Path | str = PATH, max_age_s: Optional[float] = None) -> Optional[dict]:
        q = QuoteStore.load(path).get(_to_occ(symbol))
        if q is None:
            return None
        if max_age_s is not None:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(q["ts"])).total_seconds()
            except Exception:
                return None
            if age > max_age_s:
                return None
        return q


def spread_bps(q: dict) -> Optional[float]:
    mid = (q["bid"] + q["ask"]) / 2
    if not mid or q["ask"] < q["bid"]:
        return None
    return (q["ask"] - q["bid"]) / mid * 1e4
