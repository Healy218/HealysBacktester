"""V6 must consume the same frozen DTE choices and trusted feed timestamps."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd
import pytest

from nn_meta import config
from nn_meta.live.v4_scan import candidate_frame
from nn_meta.live.feeds.quotestore import QuoteStore, spread_bps


def test_v6_live_identity_and_campaign_bundle_are_isolated():
    environment = dict(os.environ, NN_META_POOL="v6", NN_META_CAMPAIGN="live-test")
    result = subprocess.run([sys.executable, "-c", "from nn_meta.live import v4_scan as s; import json; print(json.dumps([s.EXPERT,s.ALERT_STATE.name,str(s.DEFAULT_BUNDLE_DIR)]))"],
                            env=environment, text=True, capture_output=True, check=True)
    expert, state, bundle = json.loads(result.stdout.strip().splitlines()[-1])
    assert expert == "v6" and state == ".v6_alert_state.json"
    assert Path(bundle).parts[-4:] == ("campaigns", "live-test", "v6", "model_final")


def test_stock_feed_includes_explicit_campaign_spec_and_refuses_missing(monkeypatch, tmp_path):
    from nn_meta.live.feeds.stock_stream import union_universe, heartbeat_path
    from nn_meta.live.feeds.barstore import BarStore
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "CAMPAIGN", "")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"symbols": {"SPY": {}, "NEW": {}}}))
    assert union_universe([spec]) == ["NEW", "SPY"]
    with pytest.raises(FileNotFoundError):
        union_universe([tmp_path / "missing.json"])
    assert heartbeat_path(BarStore(tmp_path)) == tmp_path / "stock_stream.heartbeat.json"


def test_weekly_live_grid_uses_frozen_membership(monkeypatch):
    monkeypatch.setattr(config, "WEEKLY_DTE_ENABLED", True)
    monkeypatch.setattr(config, "DTE_GRID", [1, 5, 10, 30, 45])
    monkeypatch.setattr(config, "DTE_GRID_WEEKLY", [2, 4, 7])
    fresh = [{"symbol": symbol, "strategy": "rsi", "direction": 0,
              "entry_ts": pd.Timestamp("2026-09-08 14:00"), "spot": 100.,
              "bars_since_signal": 4} for symbol in ["SPY", "ABC"]]
    frame = candidate_frame(fresh, {"weekly_symbols": ["SPY"]})
    assert set(frame[frame.symbol == "SPY"].dte) == {1, 2, 4, 5, 7, 10, 30, 45}
    assert set(frame[frame.symbol == "ABC"].dte) == {1, 5, 10, 30, 45}
    with pytest.raises(ValueError, match="frozen baseline spec"):
        candidate_frame(fresh)


@pytest.mark.parametrize("heartbeat", [
    {"ts": "2026-09-08T14:30:01+00:00"},
    {"ts": "invalid"}, {"ts": "2026-09-08T14:30:00"},
    {"ts": "2026-09-08T14:30:00+00:00", "state": "reconnecting"},
    {"ts": "2026-09-08T14:30:00+00:00", "state": "connecting"},
])
def test_untrusted_stock_heartbeat_uses_rest(monkeypatch, heartbeat):
    from nn_meta.live.run_live import _feed_is_fresh
    monkeypatch.setattr("nn_meta.live.feeds.barstore.read_heartbeat", lambda _: heartbeat)
    assert not _feed_is_fresh(datetime(2026, 9, 8, 14, 30, tzinfo=timezone.utc))


def test_out_of_order_quote_cannot_replace_newer_observation(tmp_path):
    path = tmp_path / "quotes.json"
    store = QuoteStore(path)
    for bid, stamp in [(1.1, "2026-09-08T14:30:25.000000002Z"), (1.0, "2026-09-08T14:30:25.000000001Z")]:
        store.update("o:spy260918c00650000", bid=bid, ask=1.2, bid_size=1, ask_size=1, ts=stamp)
    store.flush()
    result = QuoteStore.get("SPY260918C00650000", path, 10, now="2026-09-08T14:30:30Z")
    assert result["bid"] == 1.1


@pytest.mark.parametrize("bid,ask,size", [(0, 1.2, 1), (1.3, 1.2, 1), (1.1, 1.2, 0), (float("nan"), 1.2, 1)])
def test_latest_cancelled_or_invalid_quote_does_not_expose_older_quote(tmp_path, bid, ask, size):
    path = tmp_path / "quotes.json"
    store = QuoteStore(path)
    store.update("SPY260918C00650000", bid=1.0, ask=1.2, bid_size=1, ask_size=1, ts="2026-09-08T14:30:24Z")
    store.update("SPY260918C00650000", bid=bid, ask=ask, bid_size=size, ask_size=size, ts="2026-09-08T14:30:25Z")
    store.flush()
    assert QuoteStore.get("SPY260918C00650000", path, 10, now="2026-09-08T14:30:30Z") is None


def test_future_quote_one_nanosecond_is_unavailable(tmp_path):
    path = tmp_path / "quotes.json"
    store = QuoteStore(path)
    store.update("SPY260918C00650000", bid=1.1, ask=1.2, bid_size=1, ask_size=1,
                 ts="2026-09-08T14:30:30.000000001Z")
    store.flush()
    assert QuoteStore.get("SPY260918C00650000", path, now="2026-09-08T14:30:30Z") is None
    assert spread_bps({"bid": -2, "ask": -1}) is None


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), "bad", 10**400])
def test_invalid_new_observation_replaces_old_quote_and_writes_strict_json(tmp_path, invalid):
    path = tmp_path / "quotes.json"
    store = QuoteStore(path)
    store.update("SPY260918C00650000", bid=1., ask=1.2, bid_size=1, ask_size=1,
                 ts="2026-09-08T14:30:00Z")
    store.update("SPY260918C00650000", bid=invalid, ask=1.2, bid_size=1, ask_size=1,
                 ts="2026-09-08T14:30:01Z")
    store.flush()
    def reject_constant(value):
        raise ValueError(value)
    assert json.loads(path.read_text(), parse_constant=reject_constant)["SPY260918C00650000"]["bid"] is None
    assert QuoteStore.get("SPY260918C00650000", path, now="2026-09-08T14:30:02Z") is None
