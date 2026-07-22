"""Durable live-scanner state: alert dedupe, outbox, paper ledger, drift/health."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from nn_meta.live.state import (AlertState, Outbox, PaperLedger,
                                health_snapshot, population_stability_index)


def test_alert_state_is_idempotent_and_survives_reload(tmp_path):
    path = tmp_path / "alerts.json"
    a = AlertState(path)
    assert a.mark("SPY|2026-01-08|rsi") is True     # first time -> alert
    assert a.mark("SPY|2026-01-08|rsi") is False     # duplicate -> suppressed
    # A restart rebuilds the dedupe set from disk.
    assert AlertState(path).seen("SPY|2026-01-08|rsi")
    assert AlertState(path).mark("SPY|2026-01-08|rsi") is False


def test_outbox_dedupes_and_tracks_acknowledgement(tmp_path):
    path = tmp_path / "outbox.json"
    box = Outbox(path)
    first = box.enqueue({"text": "hi"}, key="sig-1")
    again = box.enqueue({"text": "hi"}, key="sig-1")   # same key -> same entry
    assert first == again
    assert len(box.unacked()) == 1
    box.mark_sent(first)
    assert len(box.unacked()) == 1                       # sent but not acked -> still replayed
    box.acknowledge(first)
    assert box.unacked() == []
    # Unacked entries replay after a restart.
    box2 = Outbox(path)
    box2.enqueue({"text": "later"}, key="sig-2")
    assert {e["payload"]["text"] for e in Outbox(path).unacked()} == {"later"}


def test_paper_ledger_pnl_and_equity(tmp_path):
    path = tmp_path / "ledger.json"
    led = PaperLedger(path)
    led.open("t1", "SPY", "2026-01-08T10:00", 1.00, qty=2.0)
    led.open("t2", "QQQ", "2026-01-08T10:00", 2.00)
    led.close("t1", "2026-01-09T10:00", 1.50)
    assert led.realized_pnl() == pytest.approx((1.50 - 1.00) * 2.0)
    assert len(led.open_positions()) == 1
    # Equity = cash + realized + unrealized (QQQ marked up 0.5).
    assert led.equity(100.0, marks={"QQQ": 2.5}) == pytest.approx(100.0 + 1.0 + 0.5)
    assert PaperLedger(path).realized_pnl() == pytest.approx(1.0)  # persisted


def test_paper_ledger_guards(tmp_path):
    led = PaperLedger(tmp_path / "l.json")
    led.open("t1", "SPY", "2026-01-08", 1.0)
    with pytest.raises(ValueError, match="already recorded"):
        led.open("t1", "SPY", "2026-01-08", 1.0)
    with pytest.raises(KeyError, match="no open trade"):
        led.close("ghost", "2026-01-09", 1.0)


def test_psi_zero_when_identical_and_large_under_shift():
    rng = np.random.default_rng(0)
    ref = rng.normal(0, 1, 5000)
    assert population_stability_index(ref, ref) == pytest.approx(0.0, abs=1e-9)
    shifted = rng.normal(2.0, 1, 5000)
    assert population_stability_index(ref, shifted) > 0.25   # material drift


def test_health_snapshot_flags_staleness_and_errors():
    now = datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc)
    fresh = health_snapshot(last_run_ts=now - timedelta(minutes=5), now=now,
                            error_count=0, scanned=120, alerted=3)
    assert fresh["healthy"] and not fresh["stale"]
    stale = health_snapshot(last_run_ts=now - timedelta(hours=2), now=now)
    assert stale["stale"] and not stale["healthy"]
    errored = health_snapshot(last_run_ts=now, now=now, error_count=2)
    assert not errored["healthy"]
