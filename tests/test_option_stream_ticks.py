import asyncio
import json
from types import SimpleNamespace

import msgpack
import pandas as pd
import pytest

from nn_meta.live.feeds import option_stream
from nn_meta.live.feeds.tick_journal import TickJournal

A = "SPY260918C00500000"
B = "SPY260918P00500000"
EVENT = pd.Timestamp("2026-09-05T14:00:00.123456789Z").value
RECEIPT = EVENT + 10_000


class Store:
    def __init__(self):
        self.updates = []
        self.flushes = 0

    def update(self, contract, **fields):
        self.updates.append((contract, fields))

    def flush(self):
        self.flushes += 1


@pytest.fixture
def stream_harness(monkeypatch):
    instances, heartbeats = [], []
    messages = {"quotes": True, "trades": True}

    class FakeStream:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs
            self.quote_handlers, self.trade_handlers = {}, {}
            self.calls = []
            self.closed = False
            instances.append(self)

        def subscribe_quotes(self, handler, *symbols):
            self.calls.append(("quotes_add", symbols))
            self.quote_handlers.update(dict.fromkeys(symbols, handler))

        def unsubscribe_quotes(self, *symbols):
            self.calls.append(("quotes_drop", symbols))
            for symbol in symbols:
                self.quote_handlers.pop(symbol, None)

        def subscribe_trades(self, handler, *symbols):
            self.calls.append(("trades_add", symbols))
            self.trade_handlers.update(dict.fromkeys(symbols, handler))

        def unsubscribe_trades(self, *symbols):
            self.calls.append(("trades_drop", symbols))
            for symbol in symbols:
                self.trade_handlers.pop(symbol, None)

        async def _run_forever(self):
            if messages["quotes"]:
                for symbol, handler in list(self.quote_handlers.items()):
                    if self.kwargs["raw_data"]:
                        q = {"T": "q", "S": symbol, "t": msgpack.Timestamp(EVENT // 10**9, EVENT % 10**9),
                             "bp": 1.2, "ap": 1.3, "bs": 3, "as": 8, "c": "R"}
                    else:
                        q = SimpleNamespace(symbol=symbol, timestamp=pd.Timestamp(EVENT, tz="UTC").to_pydatetime(warn=False),
                                            bid_price=1.2, ask_price=1.3, bid_size=3, ask_size=8)
                    await handler(q)
            if messages["trades"]:
                for symbol, handler in list(self.trade_handlers.items()):
                    await handler({"T": "t", "S": symbol,
                                   "t": msgpack.Timestamp(EVENT // 10**9, EVENT % 10**9),
                                   "p": 1.3, "s": 5, "c": "SL"})
            await asyncio.Event().wait()

        async def close(self):
            self.closed = True

    monkeypatch.setenv("ALPACA_API_KEY", "test")
    monkeypatch.setenv("ALPACA_API_SECRET", "test")
    monkeypatch.setattr("alpaca.data.live.OptionDataStream", FakeStream)
    monkeypatch.setattr(option_stream, "write_heartbeat", lambda path, **fields: heartbeats.append(fields))
    monkeypatch.setattr(option_stream, "FLUSH_S", 0)
    monkeypatch.setattr(option_stream, "REFRESH_S", 0)
    monkeypatch.setattr(option_stream.time, "time_ns", lambda: RECEIPT)
    return instances, heartbeats, messages


def test_default_stream_stays_model_quotes_only(stream_harness):
    instances, heartbeats, _ = stream_harness
    store = Store()
    asyncio.run(option_stream._serve(store, ["O:" + A, A], .001))
    stream = instances[0]
    assert stream.kwargs["raw_data"] is False
    assert stream.calls == [("quotes_add", (A,))]
    assert len(store.updates) == 1 and stream.closed
    assert heartbeats[-1]["quotes"] == heartbeats[-1]["received_quotes"] == 1
    assert heartbeats[-1]["trades"] == 0 and not heartbeats[-1]["tick_recording"]
    assert heartbeats[-1]["actual_data_received"]


def test_recording_adds_trades_preserves_ns_and_updates_store(stream_harness, tmp_path):
    instances, heartbeats, _ = stream_harness
    store = Store()
    with TickJournal(tmp_path) as journal:
        asyncio.run(option_stream._serve(store, [A], .001, journal))
    assert instances[0].kwargs["raw_data"] is True
    assert ("trades_add", (A,)) in instances[0].calls
    assert store.updates[0][1]["ts"].value == EVENT
    q = json.loads((tmp_path / "2026-09-05" / "quotes.jsonl").read_text())
    t = json.loads((tmp_path / "2026-09-05" / "trades.jsonl").read_text())
    assert q["event_timestamp_ns"] == t["event_timestamp_ns"] == EVENT
    assert q["received_at_ns"] == t["received_at_ns"] == RECEIPT
    assert heartbeats[-1]["last_quote_received_ns"] == RECEIPT
    assert heartbeats[-1]["last_trade_event_ns"] == EVENT
    assert heartbeats[-1]["tick_journal"]["fsynced_rows"] == 2
    assert not heartbeats[-1]["tick_journal"]["coverage_complete"]


def test_journal_disk_error_is_visible_without_losing_latest_quote(stream_harness, tmp_path, monkeypatch):
    _, heartbeats, _ = stream_harness
    store = Store()
    with TickJournal(tmp_path) as journal:
        def broken(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(journal, "record", broken)
        asyncio.run(option_stream._serve(store, [A], .001, journal))
    assert len(store.updates) == 1
    assert heartbeats[-1]["journal_errors"] == 2
    assert "disk full" in heartbeats[-1]["last_journal_error"]
    assert heartbeats[-1]["tick_journal"]["appended_quotes"] == 0


def test_quiet_connection_heartbeat_does_not_imply_received_ticks(stream_harness, tmp_path):
    _, heartbeats, messages = stream_harness
    messages.update(quotes=False, trades=False)
    with TickJournal(tmp_path) as journal:
        asyncio.run(option_stream._serve(Store(), [A], .001, journal))
    assert all(not beat["actual_data_received"] for beat in heartbeats)
    assert heartbeats[-1]["last_quote_received_ns"] is None
    assert heartbeats[-1]["last_trade_received_ns"] is None
    assert heartbeats[-1]["tick_journal"]["last_received_at_ns"] is None


def test_dynamic_watch_preserves_quotes_when_daily_trade_budget_is_spent(stream_harness, tmp_path, monkeypatch):
    instances, heartbeats, _ = stream_harness
    watch = iter([[A], [B]])
    monkeypatch.setattr(option_stream, "read_watch", lambda: next(watch))
    with TickJournal(tmp_path, max_contracts=1) as journal:
        asyncio.run(option_stream._serve(Store(), None, .001, journal))
    calls = instances[0].calls
    assert ("quotes_add", (B,)) in calls and ("quotes_drop", (A,)) in calls
    assert ("trades_drop", (A,)) in calls and ("trades_add", (B,)) not in calls
    assert heartbeats[-1]["contracts"] == 1 and heartbeats[-1]["trade_contracts"] == 0
    assert heartbeats[-1]["tick_journal"]["refused_daily_limit"] == 1


def test_fixed_watch_is_capped_like_dynamic_watch(stream_harness, monkeypatch):
    instances, _, _ = stream_harness
    monkeypatch.setattr(option_stream, "MAX_CONTRACTS", 1)
    asyncio.run(option_stream._serve(Store(), [A, B], .001))
    assert instances[0].calls == [("quotes_add", (A,))]
