import json
import sqlite3
from types import SimpleNamespace

import pytest

from integrations.alpaca_paper.v6_preflight import paper_account_snapshot, read_v6_positions


def test_v6_preflight_reads_without_mutation_and_shows_whole_contract_gap(tmp_path):
    path = tmp_path / "portfolio.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE metadata(key TEXT,value TEXT); CREATE TABLE positions(key TEXT,symbol TEXT,state TEXT,payload TEXT);")
        db.execute("INSERT INTO metadata VALUES('equity','1.2')")
        for key, state, price in (("cheap", "open", 5), ("dear", "open", 20), ("done", "closed", 1)):
            payload = dict(initial_amount=.1, size_fraction=.1, entry_price=price, contract=key.upper() + "261016C00100000",
                           opened_at="2026-09-24T15:00:00+00:00")
            db.execute("INSERT INTO positions VALUES(?,?,?,?)", (key, key, state, json.dumps(payload)))
    before = path.read_bytes()
    result = read_v6_positions(path, capital=10_000)
    assert path.read_bytes() == before
    assert result["active_positions"] == 2
    assert result["zero_contract_positions"] == 1
    assert [p["indicative_whole_contracts"] for p in result["positions"]] == [2, 0]
    assert all(p["historical_only"] for p in result["positions"])
    broker = read_v6_positions(path, capital=100_000, sizing_source="paper_buying_power")
    assert broker["sizing_source"] == "paper_buying_power"
    assert [p["indicative_whole_contracts"] for p in broker["positions"]] == [20, 5]


def test_account_snapshot_is_paper_only_and_read_only(monkeypatch):
    from alpaca.trading import client as client_module

    calls = []

    class FakeClient:
        def __init__(self, key, secret, *, paper):
            calls.append((key, secret, paper))

        def get_account(self):
            return SimpleNamespace(id="paper-account-id", status="ACTIVE", trading_blocked=False, account_blocked=False,
                options_trading_level=2, options_approved_level=2, options_buying_power="9000",
                cash="10000", equity="10000")

        def get_all_positions(self):
            return []

        def get_orders(self, *, filter):
            assert filter.status.value == "open"
            return []

        def get_option_contract(self, symbol):
            return SimpleNamespace(status="active", tradable=True, size="100")

    monkeypatch.setattr(client_module, "TradingClient", FakeClient)
    result = paper_account_snapshot("paper-key", "paper-secret", contracts=("TEST261016C00100000",))
    assert calls == [("paper-key", "paper-secret", True)]
    assert result["long_option_entry_eligible"]
    assert result["position_count"] == result["open_order_count"] == 0
    assert result["contract_checks"] == [{"symbol": "TEST261016C00100000", "listed": True,
        "status": "active", "tradable": True, "multiplier": "100"}]
    assert "paper-key" not in json.dumps(result) and "paper-secret" not in json.dumps(result)
    assert len(result["account_fingerprint"]) == 64


def test_paper_credentials_are_required():
    with pytest.raises(ValueError, match="dedicated Alpaca paper"):
        paper_account_snapshot("", "")
