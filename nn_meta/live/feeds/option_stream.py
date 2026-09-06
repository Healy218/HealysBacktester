"""Alpaca OPRA option quote stream → QuoteStore, for a DYNAMIC contract set.

    ./venv/bin/python -m nn_meta.live.feeds.option_stream [--contracts A,B] [--run-seconds N]
    # Optional quotes AND trades, append-only with event/receipt nanoseconds:
    ./venv/bin/python -m nn_meta.live.feeds.option_stream --record-ticks

The subscription set is everything the panel currently cares about — OCC
symbols listed in ``nn_meta/live/feeds/data/option_watch.json`` (written by
the experts' alert path and the paper seat: recent alerts' contracts, open
paper positions) — capped at ``MAX_CONTRACTS`` (Algo Trader Plus: 1,000 quote
symbols; no wildcard for option quotes). The file is re-read every
``REFRESH_S`` seconds and the subscription diffed. Latest NBBO per contract
is flushed every ``FLUSH_S`` seconds. Tick recording is opt-in and adds trade
subscriptions only for the journal's bounded daily contract set. QuoteStore
continues to cover the full watch set. A heartbeat records process progress;
actual receipt times and journal errors are separate and never certify coverage.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from utils.logging_utils import setup_logging
from nn_meta.live.feeds.barstore import write_heartbeat
from nn_meta.live.feeds.quotestore import QuoteStore, ROOT, HEARTBEAT, _to_occ
from nn_meta.live.feeds.tick_journal import TickJournal, event_timestamp_ns

logger = setup_logging(log_file="logs/backtester.log")
_TAG = "feed-options"
WATCH = ROOT / "option_watch.json"
MAX_CONTRACTS = 1000
REFRESH_S = 30
FLUSH_S = 5


def read_watch(path: Path = WATCH) -> list[str]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        syms = raw if isinstance(raw, list) else raw.get("contracts", [])
        return sorted({_to_occ(s) for s in syms})[:MAX_CONTRACTS]
    except Exception as e:
        logger.warning(f"[{_TAG}] {path}: {e}")
        return []


def add_to_watch(contracts, path: Path = WATCH) -> int:
    """Alert path / paper seat: register contracts to stream. Idempotent."""
    cur = set(read_watch(path))
    cur |= {_to_occ(c) for c in contracts}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps({"contracts": sorted(cur)[:MAX_CONTRACTS],
                               "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}))
    os.replace(tmp, path)
    return len(cur)


async def _serve(store: QuoteStore, fixed: list[str] | None, run_seconds: float | None,
                 journal: TickJournal | None = None) -> None:
    from alpaca.data.live import OptionDataStream
    from alpaca.data.enums import OptionsFeed
    stream = OptionDataStream(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"],
                              feed=OptionsFeed.OPRA, raw_data=journal is not None)
    n = {"quotes": 0, "received_quotes": 0, "trades": 0, "journal_errors": 0,
         "last_quote_received_ns": None, "last_trade_received_ns": None,
         "last_quote_event_ns": None, "last_trade_event_ns": None,
         "last_journal_error": None}

    def journal_error(exc):
        n["journal_errors"] += 1
        n["last_journal_error"] = repr(exc)[:200]
        logger.error(f"[{_TAG}] tick journal: {exc!r}")

    def record(raw, received, monotonic):
        try:
            journal.record(raw, received_at_ns=received, received_monotonic_ns=monotonic)
        except Exception as exc:
            journal_error(exc)

    async def on_quote(q):
        received, monotonic = time.time_ns(), time.monotonic_ns()
        n["received_quotes"] += 1
        n["last_quote_received_ns"] = received
        if journal is not None:
            record(q, received, monotonic)
        try:
            if journal is not None:
                event = event_timestamp_ns(q.get("t"))
                n["last_quote_event_ns"] = event
                store.update(q["S"], bid=q.get("bp") or 0.0, ask=q.get("ap") or 0.0,
                             bid_size=q.get("bs") or 0, ask_size=q.get("as") or 0,
                             ts=pd.Timestamp(event, tz="UTC"))
            else:
                n["last_quote_event_ns"] = event_timestamp_ns(q.timestamp)
                store.update(q.symbol, bid=q.bid_price or 0.0, ask=q.ask_price or 0.0,
                             bid_size=q.bid_size or 0, ask_size=q.ask_size or 0, ts=q.timestamp)
            n["quotes"] += 1
        except Exception as e:
            logger.error(f"[{_TAG}] {getattr(q, 'symbol', '?')}: {e}")

    async def on_trade(t):
        received, monotonic = time.time_ns(), time.monotonic_ns()
        n["trades"] += 1
        n["last_trade_received_ns"] = received
        record(t, received, monotonic)
        try:
            n["last_trade_event_ns"] = event_timestamp_ns(t.get("t"))
        except Exception:
            n["last_trade_event_ns"] = None

    subscribed: set[str] = set()
    trade_subscribed: set[str] = set()

    def heartbeat(state="running"):
        write_heartbeat(HEARTBEAT, **n, contracts=len(subscribed),
                        trade_contracts=len(trade_subscribed), state=state,
                        tick_recording=journal is not None,
                        actual_data_received=bool(n["received_quotes"] or n["trades"]),
                        tick_journal=journal.status() if journal is not None else None)

    def sync_subscriptions():
        want = set(sorted({_to_occ(c) for c in fixed})[:MAX_CONTRACTS]) if fixed is not None else set(read_watch())
        add, drop = want - subscribed, subscribed - want
        if add:
            stream.subscribe_quotes(on_quote, *sorted(add))
        if drop:
            stream.unsubscribe_quotes(*sorted(drop))
        subscribed.clear()
        subscribed.update(want)
        if journal is not None:
            try:
                record_want = journal.set_contracts(want)
            except Exception as exc:
                journal_error(exc)
                record_want = set()
            trade_add, trade_drop = record_want - trade_subscribed, trade_subscribed - record_want
            if trade_add:
                stream.subscribe_trades(on_trade, *sorted(trade_add))
            if trade_drop:
                stream.unsubscribe_trades(*sorted(trade_drop))
            trade_subscribed.clear()
            trade_subscribed.update(record_want)
        return len(add), len(drop)

    task = None
    try:
        sync_subscriptions()
        if journal is not None:
            try:
                journal.control("stream_start_requested", contracts=sorted(subscribed),
                                trade_contracts=sorted(trade_subscribed), coverage_complete=False)
            except Exception as exc:
                journal_error(exc)
        heartbeat("connecting")
        task = asyncio.create_task(stream._run_forever())
        t0 = time.monotonic()
        last_flush = last_refresh = t0
        while True:
            await asyncio.sleep(1)
            now = time.monotonic()
            if now - last_flush >= FLUSH_S:
                store.flush()
                if journal is not None:
                    try:
                        journal.flush()
                    except Exception as exc:
                        journal_error(exc)
                last_flush = now
                heartbeat()
            if (fixed is None or journal is not None) and now - last_refresh >= REFRESH_S:
                a, d = sync_subscriptions()
                last_refresh = now
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
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if journal is not None:
            try:
                journal.control("stream_stopped", coverage_complete=False)
                journal.flush()
            except Exception as exc:
                journal_error(exc)
        heartbeat("stopped")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", default=None, help="fixed OCC list (default: option_watch.json)")
    ap.add_argument("--run-seconds", type=float, default=None)
    ap.add_argument("--record-ticks", action="store_true", help="journal raw OPRA quotes and trades with receipt times")
    ap.add_argument("--tick-root", type=Path, default=ROOT / "option_ticks", help="append-only journal directory")
    ap.add_argument("--tick-contract-limit", type=int, default=MAX_CONTRACTS,
                    help="maximum distinct recorded contracts per UTC receipt day (1-1000)")
    args = ap.parse_args()
    fixed = [c.strip() for c in args.contracts.split(",")] if args.contracts else None
    store = QuoteStore()
    journal = TickJournal(args.tick_root, max_contracts=args.tick_contract_limit) if args.record_ticks else None
    backoff = 5.0
    try:
        while True:
            try:
                asyncio.run(_serve(store, fixed, args.run_seconds, journal))
                if args.run_seconds:
                    return
                backoff = 5.0
            except KeyboardInterrupt:
                return
            except Exception as e:
                logger.error(f"[{_TAG}] stream died: {e!r}; reconnecting in {backoff:.0f}s")
                write_heartbeat(HEARTBEAT, state="reconnecting", error=repr(e)[:200],
                                tick_recording=journal is not None,
                                tick_journal=journal.status() if journal is not None else None)
                time.sleep(backoff)
                backoff = min(backoff * 2, 120.0)
    finally:
        if journal is not None:
            journal.close()


if __name__ == "__main__":
    main()
