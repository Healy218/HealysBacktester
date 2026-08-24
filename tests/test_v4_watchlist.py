"""Dual-mode cadence: the daily watchlist digest (ROADMAP wave-2 item 5) —
recording during passes, top-N digest, forward outcome resolution, and the
idempotency that makes a re-run cron line harmless."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from nn_meta.live.v4_scan import digest_pass
from nn_meta.live.watchlist import MAX_HOLD_DAYS, Watchlist, format_digest

NOW = datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc)
TODAY = "2026-08-24"


def _record(wl, key, *, decision=0.05, direction=0, spot=100.0,
            entry_ts=None, dte=3, alerted=False, symbol="SPY"):
    wl.record(key=key, symbol=symbol, strategy="rsi", dte=dte,
              direction=direction, score=0.6, decision=decision, spot=spot,
              entry_ts=entry_ts or pd.Timestamp("2026-08-24 15:00"),
              alerted=alerted)


class _Notifier:
    def __init__(self):
        self.sent = []

    def send(self, message, title=None):
        self.sent.append((title, message))
        return True


def test_record_is_idempotent_but_upgrades_alerted(tmp_path):
    wl = Watchlist(tmp_path / "w.json")
    _record(wl, "k1", decision=0.05)
    _record(wl, "k1", decision=0.99)            # replay: ignored
    assert wl._entries["k1"]["decision"] == 0.05
    _record(wl, "k1", alerted=True)             # crash replay may upgrade
    assert wl._entries["k1"]["alerted"] is True
    # persisted: a fresh instance sees the same state
    assert Watchlist(tmp_path / "w.json")._entries["k1"]["alerted"] is True


def test_pending_digest_orders_by_decision_and_marks(tmp_path):
    wl = Watchlist(tmp_path / "w.json")
    _record(wl, "a", decision=0.02)
    _record(wl, "b", decision=0.09)
    rows = wl.pending_digest(TODAY)
    assert [r["key"] for r in rows] == ["b", "a"]
    wl.mark_digested(["a", "b"])
    assert wl.pending_digest(TODAY) == []


def test_resolution_scores_direction_on_the_underlying(tmp_path):
    wl = Watchlist(tmp_path / "w.json")
    old = pd.Timestamp("2026-08-18 15:00")
    _record(wl, "long-hit", direction=0, spot=100.0, entry_ts=old)
    _record(wl, "short-miss", direction=1, spot=100.0, entry_ts=old)
    _record(wl, "too-new", direction=0, spot=100.0,
            entry_ts=pd.Timestamp("2026-08-24 15:00"))
    idx = pd.date_range("2026-08-18 15:00", periods=10 * 48, freq="30min")
    bars = pd.DataFrame({"Close": np.linspace(100, 110, len(idx))}, index=idx)
    n = wl.resolve(lambda s: bars, NOW)
    assert n == 2
    assert wl._entries["long-hit"]["outcome"]["hit"] is True
    assert wl._entries["short-miss"]["outcome"]["hit"] is False
    assert wl._entries["too-new"]["outcome"] is None        # horizon not reached
    stats = wl.hit_stats(days=21)
    assert (stats["resolved"], stats["hits"]) == (2, 1)


def test_resolution_never_guesses_without_a_horizon_bar(tmp_path):
    wl = Watchlist(tmp_path / "w.json")
    _record(wl, "k", entry_ts=pd.Timestamp("2026-08-18 15:00"), dte=30)
    # horizon capped at MAX_HOLD_DAYS, but the bars end before it
    idx = pd.date_range("2026-08-18 15:00", periods=100, freq="1min")
    bars = pd.DataFrame({"Close": np.full(100, 100.0)}, index=idx)
    assert wl.resolve(lambda s: bars, NOW) == 0
    assert wl._entries["k"]["outcome"] is None
    assert min(30, MAX_HOLD_DAYS) == MAX_HOLD_DAYS


def test_format_digest_flags_alerted_and_states_the_metric():
    rows = [{"key": "a", "symbol": "SQ", "strategy": "rsi", "dte": 3,
             "direction": 1, "score": 0.61, "decision": 0.07, "alerted": True}]
    stats = {"window_days": 7, "resolved": 4, "hits": 3,
             "alerted_resolved": 1, "alerted_hits": 1}
    title, msg = format_digest(rows, stats, aliases={"SQ": "XYZ"}, ev_mode=True)
    assert "watchlist" in title and "XYZ" in msg and "PUT" in msg
    assert "EV +7.0%" in msg and "⚡" in msg
    assert "75%" in msg and "underlying-direction" in msg   # honest metric label


def test_digest_pass_sends_once_per_day(tmp_path):
    wl = Watchlist(tmp_path / ".v4_watchlist.json")
    _record(wl, "a", decision=0.09, alerted=True)
    _record(wl, "b", decision=0.02)
    notifier = _Notifier()
    bars = pd.DataFrame({"Close": [100.0]},
                        index=[pd.Timestamp("2026-08-24 15:00")])
    s1 = digest_pass(bar_loader=lambda s: bars, notifier=notifier,
                     state_dir=tmp_path, top=10, now=NOW)
    assert s1["signals_today"] == 2 and s1["delivered"] == 1
    assert "top 2 of 2" in notifier.sent[0][0]
    # second run the same day: nothing pending, outbox key dedupes
    s2 = digest_pass(bar_loader=lambda s: bars, notifier=notifier,
                     state_dir=tmp_path, top=10, now=NOW)
    assert s2["signals_today"] == 0 and s2["delivered"] == 0
    assert len(notifier.sent) == 1


def test_digest_pass_quiet_day_sends_nothing(tmp_path):
    notifier = _Notifier()
    s = digest_pass(bar_loader=lambda s: pd.DataFrame(), notifier=notifier,
                    state_dir=tmp_path, now=NOW)
    assert s["signals_today"] == 0 and notifier.sent == []
