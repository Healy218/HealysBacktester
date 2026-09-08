"""Alpaca OPRA option quote stream → QuoteStore, for a DYNAMIC contract set.

    ./venv/bin/python -m nn_meta.live.feeds.option_stream [--contracts A,B] [--run-seconds N]

The subscription set is everything the panel currently cares about — OCC
symbols listed in ``nn_meta/live/feeds/data/option_watch.json`` (written by
the experts' alert path and the paper seat: recent alerts' contracts, open
paper positions) — capped at ``MAX_CONTRACTS`` (Algo Trader Plus: 1,000 quote
symbols; no wildcard for option quotes). The file is re-read every
``REFRESH_S`` seconds and the subscription diffed. Latest NBBO per contract
is flushed every ``FLUSH_S`` seconds. Heartbeat like the stock stream.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from utils.logging_utils import setup_logging
from nn_meta.live.feeds.barstore import write_heartbeat
from nn_meta.live.feeds.quotestore import QuoteStore, ROOT, HEARTBEAT, _to_occ

logger = setup_logging(log_file="logs/backtester.log")
_TAG = "feed-options"
WATCH = ROOT / "option_watch.json"
MAX_CONTRACTS = 1000
REFRESH_S = 30
FLUSH_S = 5
IDLE_POLL_S = 30          # how often an idle stream re-reads the watch list


def read_watch(path: Path | None = None) -> list[str]:
    path = Path(path) if path is not None else WATCH      # resolved per call (tests monkeypatch WATCH)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        syms = raw if isinstance(raw, list) else raw.get("contracts", [])
        return sorted({_to_occ(s) for s in syms})[:MAX_CONTRACTS]
    except Exception as e:
        logger.warning(f"[{_TAG}] {path}: {e}")
        return []


def add_to_watch(contracts, path: Path | None = None) -> int:
    """Alert path / paper seat: register contracts to stream. Idempotent."""
    path = Path(path) if path is not None else WATCH
    cur = set(read_watch(path))
    cur |= {_to_occ(c) for c in contracts}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps({"contracts": sorted(cur)[:MAX_CONTRACTS],
                               "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}))
    os.replace(tmp, path)
    return len(cur)


async def _serve(store: QuoteStore, fixed: list[str] | None, run_seconds: float | None) -> None:
    from alpaca.data.live import OptionDataStream
    from alpaca.data.enums import OptionsFeed
    stream = OptionDataStream(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"],
                              feed=OptionsFeed.OPRA)
    n = {"quotes": 0}

    async def on_quote(q):
        try:
            store.update(q.symbol, bid=q.bid_price or 0.0, ask=q.ask_price or 0.0,
                         bid_size=q.bid_size or 0, ask_size=q.ask_size or 0, ts=q.timestamp)
            n["quotes"] += 1
        except Exception as e:
            logger.error(f"[{_TAG}] {getattr(q, 'symbol', '?')}: {e}")

    subscribed: set[str] = set()

    def sync_subscriptions():
        want = set(fixed) if fixed is not None else set(read_watch())
        add, drop = want - subscribed, subscribed - want
        if add:
            stream.subscribe_quotes(on_quote, *sorted(add))
        if drop:
            stream.unsubscribe_quotes(*sorted(drop))
        subscribed.clear(); subscribed.update(want)
        return len(add), len(drop)

    sync_subscriptions()
    t0 = time.time()
    # Gate (2026-09-08 review, fix 1): alpaca-py's _run_forever spins on
    # `await asyncio.sleep(0)` until the first subscription exists — with an
    # empty watch list that pinned a full core for three days while streaming
    # nothing. Idle here (heartbeat state "idle") until the alert path
    # registers a contract, then start the websocket loop.
    while not subscribed:
        write_heartbeat(HEARTBEAT, quotes=0, contracts=0, state="idle")
        if run_seconds and time.time() - t0 >= run_seconds:
            return
        await asyncio.sleep(min(IDLE_POLL_S, run_seconds) if run_seconds else IDLE_POLL_S)
        sync_subscriptions()
    logger.info(f"[{_TAG}] starting stream with {len(subscribed)} contract(s)")
    write_heartbeat(HEARTBEAT, quotes=0, contracts=len(subscribed), state="connecting")
    task = asyncio.create_task(stream._run_forever())
    last_flush = last_refresh = time.time()
    try:
        while True:
            await asyncio.sleep(1)
            now = time.time()
            if now - last_flush >= FLUSH_S:
                store.flush(); last_flush = now
                write_heartbeat(HEARTBEAT, quotes=n["quotes"], contracts=len(subscribed))
            if fixed is None and now - last_refresh >= REFRESH_S:
                a, d = sync_subscriptions(); last_refresh = now
                if a or d:
                    logger.info(f"[{_TAG}] subscriptions +{a} -{d} → {len(subscribed)}")
            if task.done():
                exc = task.exception()
                raise RuntimeError(f"stream task ended: {exc!r}")
            if run_seconds and now - t0 >= run_seconds:
                return
    finally:
        store.flush()
        try:
            await stream.close()
        except Exception:
            pass
        task.cancel()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", default=None, help="fixed OCC list (default: option_watch.json)")
    ap.add_argument("--run-seconds", type=float, default=None)
    args = ap.parse_args()
    fixed = [c.strip() for c in args.contracts.split(",")] if args.contracts else None
    store = QuoteStore()
    backoff = 5.0
    while True:
        try:
            asyncio.run(_serve(store, fixed, args.run_seconds))
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


if __name__ == "__main__":
    main()
