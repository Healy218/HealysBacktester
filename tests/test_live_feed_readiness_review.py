import asyncio
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.live.feeds import stock_stream
from nn_meta.live.feeds.barstore import BarStore
from nn_meta.live.feeds.quotestore import QuoteStore
from nn_meta.live.run_live import _feed_is_fresh


def test_stock_backfill_requests_raw_basis(monkeypatch, tmp_path):
    requests = []

    class Client:
        def __init__(self, *args):
            pass

        def get_stock_bars(self, request):
            requests.append(request)
            return SimpleNamespace(data={})

    monkeypatch.setenv("ALPACA_API_KEY", "test")
    monkeypatch.setenv("ALPACA_API_SECRET", "test")
    monkeypatch.setattr("alpaca.data.historical.StockHistoricalDataClient", Client)
    assert stock_stream.backfill_today(BarStore(tmp_path), ["SPY"], "2026-09-08") == 0
    assert len(requests) == 1 and requests[0].adjustment.value == "raw"


@pytest.fixture
def stock_stream_harness(monkeypatch, tmp_path):
    heartbeats, streams = [], []
    behavior = {"fail": False, "quiet": False, "return": False}

    class Stream:
        def __init__(self, *args, **kwargs):
            self.handler = None
            self.closed = False
            streams.append(self)

        def subscribe_bars(self, handler, *symbols):
            self.handler = handler

        async def _run_forever(self):
            if behavior["fail"]:
                raise RuntimeError("test authentication failure")
            if behavior["return"]:
                return
            if not behavior["quiet"]:
                await self.handler(SimpleNamespace(symbol="SPY", timestamp=pd.Timestamp("2026-09-08T14:30Z"),
                    open=1., high=1., low=1., close=1., volume=1.))
            await asyncio.Event().wait()

        async def close(self):
            self.closed = True

    monkeypatch.setenv("ALPACA_API_KEY", "test")
    monkeypatch.setenv("ALPACA_API_SECRET", "test")
    monkeypatch.setattr("alpaca.data.live.StockDataStream", Stream)
    monkeypatch.setattr(stock_stream, "write_heartbeat", lambda path, **fields: heartbeats.append(fields))
    return BarStore(tmp_path), streams, heartbeats, behavior


def test_first_stock_bar_marks_single_symbol_stream_as_receiving(stock_stream_harness):
    store, streams, heartbeats, _ = stock_stream_harness
    asyncio.run(stock_stream._serve(store, ["SPY"], .02))
    running = [beat for beat in heartbeats if beat["state"] == "running"]
    assert len(running) == 1
    assert running[0]["bars"] == 1 and running[0]["actual_data_received"]
    assert isinstance(running[0]["last_received_at_ns"], int)
    assert streams[0].closed and heartbeats[-1]["state"] == "stopped"


@pytest.mark.parametrize("behavior,match", [("fail", "authentication failure"), ("return", "ended before")])
def test_stock_probe_does_not_succeed_after_stream_failure(stock_stream_harness, behavior, match):
    store, streams, heartbeats, flags = stock_stream_harness
    flags[behavior] = True
    with pytest.raises(RuntimeError, match=match):
        asyncio.run(stock_stream._serve(store, ["SPY"], .1))
    assert streams[0].closed and heartbeats[-1]["state"] == "stopped"


def test_quiet_stock_probe_does_not_fabricate_receipt(stock_stream_harness):
    store, _, heartbeats, flags = stock_stream_harness
    flags["quiet"] = True
    asyncio.run(stock_stream._serve(store, ["SPY"], .01))
    assert all(not beat["actual_data_received"] for beat in heartbeats)


@pytest.mark.parametrize("heartbeat", [
    {"ts": "2026-09-08T14:30:00.000000001Z"},
    {"ts": "2026-09-08T14:26:59.999999999Z"},
    {"ts": "2026-09-08T14:30:00Z", "state": "stopped"},
    [], {"ts": "NaT"},
])
def test_heartbeat_exact_clock_boundaries_and_stopped_state(monkeypatch, heartbeat):
    monkeypatch.setattr("nn_meta.live.feeds.barstore.read_heartbeat", lambda _: heartbeat)
    assert not _feed_is_fresh(datetime(2026, 9, 8, 14, 30, tzinfo=timezone.utc))


def test_heartbeat_exact_age_limit_remains_valid(monkeypatch):
    monkeypatch.setattr("nn_meta.live.feeds.barstore.read_heartbeat",
                        lambda _: {"ts": "2026-09-08T14:27:00Z", "state": "running"})
    assert _feed_is_fresh(datetime(2026, 9, 8, 14, 30, tzinfo=timezone.utc))


@pytest.mark.parametrize("payload", [[], "bad", {"SPY260918C00500000": []},
    {"SPY260918C00500000": {"bid": 10**400, "ask": 1, "bid_size": 1, "ask_size": 1}}])
def test_malformed_quote_cache_is_unavailable_instead_of_crashing(tmp_path, payload):
    path = tmp_path / "quotes.json"
    path.write_text(json.dumps(payload))
    assert QuoteStore.get("SPY260918C00500000", path, now="2026-09-08T14:30Z") is None
