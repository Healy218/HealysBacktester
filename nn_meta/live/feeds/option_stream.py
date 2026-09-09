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
LOOP_TICK_S = 1.0         # main loop cadence (flush/refresh/heartbeat checks)
STALL_EXIT_S = 120        # loop silent this long → exit(3) so the cron watchdog restarts us
_LAST_TICK = [time.time()]


def loop_stalled(now: float | None = None, last_tick: float | None = None,
                 limit: float = STALL_EXIT_S) -> bool:
    now = time.time() if now is None else now
    last_tick = _LAST_TICK[0] if last_tick is None else last_tick
    return now - last_tick > limit


def _stall_guard() -> None:
    """Daemon thread: a blocked event loop cannot write its own heartbeat, so
    the process looks alive to pgrep while streaming nothing (2026-09-09).
    Exit hard; the 5-minute cron watchdog restarts a dead daemon."""
    import threading
    def run():
        while True:
            time.sleep(10)
            if loop_stalled():
                logger.error(f"[{_TAG}] event loop silent for > {STALL_EXIT_S}s — exiting for restart")
                write_heartbeat(HEARTBEAT, state="stalled")
                os._exit(3)
    threading.Thread(target=run, name="option-stream-stall-guard", daemon=True).start()


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

    async def sync_subscriptions():
        want = set(fixed) if fixed is not None else set(read_watch())
        add, drop = want - subscribed, subscribed - want
        if getattr(stream, "_running", False):
            # DEADLOCK TRAP (2026-09-09): alpaca-py's subscribe_quotes /
            # unsubscribe_quotes, once the stream is running, schedule the
            # subscribe message on the event loop and then BLOCK on
            # ``.result()``. Called from inside that loop — which is where this
            # coroutine lives — the loop can never run the message and the
            # daemon froze at its first refresh (heartbeat stopped 30 s after
            # "starting stream", process alive, 0 CPU). Register the handlers
            # directly and await the send ourselves instead.
            handlers = stream._handlers["quotes"]
            for sym in add:
                handlers[sym] = on_quote
            if add:
                await stream._send_subscribe_msg()
            if drop:
                await stream._send_unsubscribe_msg("quotes", sorted(drop))
                for sym in drop:
                    handlers.pop(sym, None)
        else:
            # not running yet: the public calls only record handlers
            if add:
                stream.subscribe_quotes(on_quote, *sorted(add))
            if drop:
                stream.unsubscribe_quotes(*sorted(drop))
        subscribed.clear(); subscribed.update(want)
        return len(add), len(drop)

    await sync_subscriptions()
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
        await sync_subscriptions()
    logger.info(f"[{_TAG}] starting stream with {len(subscribed)} contract(s)")
    write_heartbeat(HEARTBEAT, quotes=0, contracts=len(subscribed), state="connecting")
    task = asyncio.create_task(stream._run_forever())
    last_flush = last_refresh = time.time()
    try:
        while True:
            await asyncio.sleep(LOOP_TICK_S)
            now = time.time()
            _LAST_TICK[0] = now
            if now - last_flush >= FLUSH_S:
                store.flush(); last_flush = now
                write_heartbeat(HEARTBEAT, quotes=n["quotes"], contracts=len(subscribed))
            if fixed is None and now - last_refresh >= REFRESH_S:
                a, d = await sync_subscriptions(); last_refresh = now
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
    _LAST_TICK[0] = time.time()
    _stall_guard()
    while True:
        _LAST_TICK[0] = time.time()
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
