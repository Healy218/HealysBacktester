"""Alpaca SIP 1-minute bar stream → BarStore (the panel's live bar feed).

    NN_META_POOL=v31 ./venv/bin/python -m nn_meta.live.feeds.stock_stream \
        [--symbols A,B] [--no-backfill] [--run-seconds N]

Symbols default to the union of every live pool's frozen universe (v3, v31,
v5 → ~443 names; Algo Trader Plus has no symbol limit on one connection).
On start it BACKFILLS today's 1m bars over REST (≤ 443 calls, seconds at
10k/min) so the store is complete from the open even after a restart, then
streams. Reconnects with backoff; writes a heartbeat JSON every bar batch
that readers use to judge freshness. Never raises out of the loop: a daemon
that dies quietly is the failure mode the 2026-09-05 stale-cache bug taught.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from utils.logging_utils import setup_logging
from nn_meta import config
from nn_meta.live.feeds.barstore import BarStore, ROOT, write_heartbeat

logger = setup_logging(log_file="logs/backtester.log")
_TAG = "feed-stocks"
HEARTBEAT = ROOT / "stock_stream.heartbeat.json"
_POOL_SPECS = ("v3", "v31", "v5", "v6")


def union_universe() -> list[str]:
    syms: set[str] = set()
    for pool in _POOL_SPECS:
        p = config.ROOT / f"artifacts_{pool}" / "baseline_spec.json"
        if p.exists():
            try:
                syms |= set(json.loads(p.read_text()).get("symbols", {}))
            except Exception as e:                       # a bad spec must not kill the feed
                logger.warning(f"[{_TAG}] {p}: {e}")
    return sorted(syms)


def backfill_today(store: BarStore, symbols: list[str], day: str | None = None) -> int:
    """Today's 1m SIP bars over REST for every symbol → store. Returns rows."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    client = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"])
    total = 0
    for i in range(0, len(symbols), 50):                 # multi-symbol requests
        chunk = symbols[i:i + 50]
        try:
            req = StockBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Minute,
                                   start=datetime.fromisoformat(f"{day}T00:00:00+00:00"),
                                   end=datetime.fromisoformat(f"{day}T23:59:59+00:00"),
                                   feed=DataFeed.SIP, adjustment="all")
            bars = client.get_stock_bars(req)
            data = bars.data if hasattr(bars, "data") else {}
            for sym, blist in data.items():
                total += store.append_1m(sym, ({"timestamp": b.timestamp, "open": b.open, "high": b.high,
                                                "low": b.low, "close": b.close, "volume": b.volume}
                                               for b in blist))
        except Exception as e:
            logger.warning(f"[{_TAG}] backfill chunk {chunk[0]}..{chunk[-1]}: {e}")
    logger.info(f"[{_TAG}] backfill {day}: {total} 1m rows over {len(symbols)} symbols")
    return total


async def _serve(store: BarStore, symbols: list[str], run_seconds: float | None) -> None:
    from alpaca.data.live import StockDataStream
    from alpaca.data.enums import DataFeed
    stream = StockDataStream(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"],
                             feed=DataFeed.SIP)
    n = {"bars": 0}

    async def on_bar(bar):
        try:
            store.append_1m(bar.symbol, [{"timestamp": bar.timestamp, "open": bar.open, "high": bar.high,
                                          "low": bar.low, "close": bar.close, "volume": bar.volume}])
            n["bars"] += 1
            if n["bars"] % 50 == 0:
                write_heartbeat(HEARTBEAT, bars=n["bars"], symbols=len(symbols),
                                last_bar=str(bar.timestamp))
        except Exception as e:
            logger.error(f"[{_TAG}] {bar.symbol}: store append failed: {e}")

    stream.subscribe_bars(on_bar, *symbols)
    write_heartbeat(HEARTBEAT, bars=0, symbols=len(symbols), state="connecting")
    task = asyncio.create_task(stream._run_forever())
    try:
        if run_seconds:
            await asyncio.sleep(run_seconds)
        else:
            await task
    finally:
        try:
            await stream.close()
        except Exception:
            pass
        task.cancel()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--no-backfill", action="store_true")
    ap.add_argument("--run-seconds", type=float, default=None, help="test: stop after N s")
    ap.add_argument("--root", default=None, help="store root (default nn_meta/live/feeds/data)")
    args = ap.parse_args()
    store = BarStore(args.root) if args.root else BarStore()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else union_universe()
    logger.info(f"[{_TAG}] {len(symbols)} symbols, store {store.root}")
    if not args.no_backfill:
        backfill_today(store, symbols)
    backoff = 5.0
    started = time.time()
    while True:
        try:
            asyncio.run(_serve(store, symbols, args.run_seconds))
            if args.run_seconds:
                return
            backoff = 5.0
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.error(f"[{_TAG}] stream died: {e!r}; reconnecting in {backoff:.0f}s")
            write_heartbeat(HEARTBEAT, state="reconnecting", error=repr(e)[:200])
            time.sleep(backoff)
            backoff = min(backoff * 2, 120.0)
        if args.run_seconds and time.time() - started > args.run_seconds:
            return


if __name__ == "__main__":
    main()
