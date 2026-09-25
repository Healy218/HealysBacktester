from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import json
import sqlite3

import pytest

from integrations.alpaca_paper.v6_bridge import (
    Journal, client_id, events_from_fresh_state, order_plan, process_events,
)


def _database(path: Path, at: datetime):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE positions (key TEXT,symbol TEXT,state TEXT,payload TEXT)")
        db.execute("CREATE TABLE events (key TEXT,recorded_at TEXT,kind TEXT,payload TEXT)")
        row = {"key": "new-signal", "opened_at": at.isoformat(), "contract": "AAPL261016C00200000",
               "size_fraction": .05, "rolls": 0, "legs": []}
        db.execute("INSERT INTO positions VALUES (?,?,?,?)", (row["key"], "AAPL", "open", json.dumps(row)))


def test_fresh_events_reject_legacy_positions(tmp_path):
    at = datetime.now(timezone.utc)
    database = tmp_path / "positions.sqlite3"
    _database(database, at)
    events = events_from_fresh_state(database, activated_at=at - timedelta(seconds=1))
    assert len(events) == 1 and events[0]["event_id"] == "new-signal|entry|0"
    with pytest.raises(ValueError, match="pre-activation"):
        events_from_fresh_state(database, activated_at=at + timedelta(seconds=1))
    assert client_id(events[0]["event_id"]) == client_id(events[0]["event_id"])


def test_preview_is_read_only_and_mark_sized(tmp_path):
    now = datetime.now(timezone.utc)
    event = {"event_id": "new-signal|entry|0", "kind": "entry", "position_key": "new-signal",
             "contract": "AAPL261016C00200000", "at": (now - timedelta(seconds=10)).isoformat(),
             "size_fraction": .05}
    account = NS(id="paper-account", status="ACTIVE", trading_blocked=False,
                 account_blocked=False, options_trading_level=3, options_buying_power="100000")
    contract = NS(tradable=True, status="active", size="100")
    quote = NS(bid_price=2.0, ask_price=2.2, bid_size=100, ask_size=10,
               timestamp=now - timedelta(seconds=1))
    snapshot = NS(latest_quote=quote, latest_trade=NS(price=2.1), mark_price=2.12)

    class Trading:
        submissions = 0
        def get_account(self): return account
        def get_all_positions(self): return []
        def get_orders(self, filter): return []
        def get_option_contract(self, symbol): return contract
        def submit_order(self, order_data):
            self.submissions += 1
            raise AssertionError("preview must never submit")

    class Data:
        def get_option_snapshot(self, request): return {event["contract"]: snapshot}

    trading = Trading()
    journal = Journal(tmp_path / "broker.sqlite3")
    result = process_events([event], journal=journal, trading=trading, data=Data(),
                            expected_fingerprint=hashlib.sha256(account.id.encode()).hexdigest(), now=now)
    assert result[0]["status"] == "preview"
    assert result[0]["plan"]["limit_price"] == "2.12"
    assert result[0]["plan"]["qty"] == 10
    assert journal.all() == [] and trading.submissions == 0
    with pytest.raises(ValueError, match="fingerprint"):
        process_events([event], journal=journal, trading=trading, data=Data(),
                       expected_fingerprint="wrong", now=now)


def test_uncertain_post_is_journaled_and_never_retried(tmp_path):
    now = datetime.now(timezone.utc)
    event = {"event_id": "future|entry|0", "kind": "entry", "position_key": "future",
             "contract": "AAPL261016C00200000", "at": now.isoformat(), "size_fraction": .05}
    account = NS(id="paper", status="ACTIVE", trading_blocked=False, account_blocked=False,
                 options_trading_level=3, options_buying_power="100000")
    snapshot = NS(latest_quote=NS(bid_price=2, ask_price=2.2, bid_size=10, ask_size=10,
                                  timestamp=now), latest_trade=None, mark_price=2.1)
    class Trading:
        calls = 0
        def get_account(self): return account
        def get_all_positions(self): return []
        def get_orders(self, filter): return []
        def get_option_contract(self, symbol): return NS(tradable=True, status="active", size="100")
        def submit_order(self, order_data):
            self.calls += 1
            raise ConnectionError("paper POST response lost")
        def get_order_by_client_id(self, client_id):
            raise LookupError("broker lookup inconclusive")
    class Data:
        def get_option_snapshot(self, request): return {event["contract"]: snapshot}
    trading = Trading()
    journal = Journal(tmp_path / "broker.sqlite3")
    fingerprint = hashlib.sha256(account.id.encode()).hexdigest()
    with pytest.raises(ConnectionError):
        process_events([event], journal=journal, trading=trading, data=Data(),
                       expected_fingerprint=fingerprint, submit=True, now=now)
    assert journal.all()[0]["state"] == "uncertain_post"
    with sqlite3.connect(journal.path) as db:
        assert db.execute("SELECT state FROM observations ORDER BY ordinal").fetchall() == [
            ("intent",), ("uncertain_post",)]
    with pytest.raises(ValueError, match="cannot be resolved"):
        process_events([event], journal=journal, trading=trading, data=Data(),
                       expected_fingerprint=fingerprint, submit=True, now=now)
    assert trading.calls == 1
