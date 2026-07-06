# tests/test_live.py
"""nn_meta.live: notifier, market-hours gating, closed-bar trimming, fresh-entry
detection, dedup, and the NN-scorer filter seam."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from nn_meta.live import scanner as sc
from nn_meta.live.notifier import (ConsoleNotifier, PushoverNotifier,
                                   get_notifier)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _bars(n=40, start="2025-06-10 14:30"):
    idx = pd.date_range(start, periods=n, freq="15min")
    return pd.DataFrame({"Open": 100.0, "High": 100.5, "Low": 99.5,
                         "Close": 100.0, "Volume": 1000}, index=idx)


def _spec_entry(dte=10):
    return {"best_strategy": "rsi",
            "strategies": {"rsi": {"params": {"rsi_window": 14},
                                   "dte": dte, "param_label": "entry=40"}}}


class _FakeResp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


class _FakeSession:
    def __init__(self, status=200):
        self.status, self.calls = status, []

    def post(self, url, data=None, timeout=None):
        self.calls.append(data)
        return _FakeResp(self.status)


# ── notifier ──────────────────────────────────────────────────────────────────

class TestNotifier:
    def test_console_always_succeeds(self, capsys):
        assert ConsoleNotifier().send("hi", "T") is True
        assert "hi" in capsys.readouterr().out

    def test_pushover_success(self):
        s = _FakeSession(200)
        assert PushoverNotifier("tok", "usr", session=s).send("m", "t") is True
        assert s.calls[0]["token"] == "tok" and s.calls[0]["message"] == "m"

    def test_pushover_http_error(self):
        assert PushoverNotifier("t", "u", session=_FakeSession(500)).send("m") is False

    def test_factory_console_when_no_creds(self, monkeypatch):
        monkeypatch.delenv("PUSHOVER_TOKEN", raising=False)
        monkeypatch.delenv("PUSHOVER_USER", raising=False)
        assert isinstance(get_notifier(), ConsoleNotifier)

    def test_factory_pushover_with_creds(self, monkeypatch):
        monkeypatch.setenv("PUSHOVER_TOKEN", "x")
        monkeypatch.setenv("PUSHOVER_USER", "y")
        assert isinstance(get_notifier(), PushoverNotifier)
        assert isinstance(get_notifier(force_console=True), ConsoleNotifier)


# ── market hours ──────────────────────────────────────────────────────────────

class TestMarketHours:
    def test_open_midday_summer(self):     # 15:00 UTC = 11:00 EDT, a Tuesday
        assert sc.is_rth(datetime(2025, 6, 10, 15, 0, tzinfo=timezone.utc))

    def test_closed_before_open(self):     # 13:00 UTC = 09:00 EDT
        assert not sc.is_rth(datetime(2025, 6, 10, 13, 0, tzinfo=timezone.utc))

    def test_closed_after_16_et(self):     # 20:30 UTC = 16:30 EDT
        assert not sc.is_rth(datetime(2025, 6, 10, 20, 30, tzinfo=timezone.utc))

    def test_closed_weekend(self):
        assert not sc.is_rth(datetime(2025, 6, 14, 15, 0, tzinfo=timezone.utc))


# ── closed-bar trimming ───────────────────────────────────────────────────────

class TestClosedBars:
    def test_drops_forming_bar(self):
        bars = _bars(4, start="2025-06-10 14:30")   # 14:30,14:45,15:00,15:15
        # now = 15:20 → the 15:15 bar (closes 15:30) is still forming
        now = datetime(2025, 6, 10, 15, 20, tzinfo=timezone.utc)
        out = sc.closed_bars(bars, now)
        assert out.index[-1] == pd.Timestamp("2025-06-10 15:00")

    def test_keeps_all_when_fully_past(self):
        bars = _bars(4)
        now = datetime(2025, 6, 11, 0, 0, tzinfo=timezone.utc)
        assert len(sc.closed_bars(bars, now)) == 4


# ── detection ─────────────────────────────────────────────────────────────────

class TestDetection:
    def test_fresh_entry_on_last_bar(self, monkeypatch):
        bars = _bars()
        last = bars.index[-1]
        monkeypatch.setattr(sc, "propose_trades",
                            lambda *a, **k: [(bars.index[5], bars.index[9], 0),
                                             (last, last, 1)])   # newest = short, last bar
        sig = sc.detect_fresh_signal("SPY", bars, _spec_entry())
        assert sig is not None
        assert sig.right == "P" and sig.direction == 1
        assert sig.bar_ts == last and sig.action == "BUY PUT"

    def test_no_signal_when_entry_is_older(self, monkeypatch):
        bars = _bars()
        monkeypatch.setattr(sc, "propose_trades",
                            lambda *a, **k: [(bars.index[5], bars.index[9], 0)])
        assert sc.detect_fresh_signal("SPY", bars, _spec_entry()) is None

    def test_no_signal_when_no_trades(self, monkeypatch):
        monkeypatch.setattr(sc, "propose_trades", lambda *a, **k: [])
        assert sc.detect_fresh_signal("SPY", _bars(), _spec_entry()) is None

    def test_alert_message_contents(self, monkeypatch):
        bars = _bars()
        monkeypatch.setattr(sc, "propose_trades",
                            lambda *a, **k: [(bars.index[-1], bars.index[-1], 0)])
        sig = sc.detect_fresh_signal("SPY", bars, _spec_entry(dte=30))
        title, msg = sc.format_alert(sig)
        assert "SPY" in title and "BUY CALL" in title
        assert "30 DTE" in msg and "rsi" in msg


# ── scanner: dedup + scorer ───────────────────────────────────────────────────

class TestScanner:
    def _scanner(self, tmp_path, monkeypatch, scorer=None, threshold=0.5):
        bars = _bars()
        monkeypatch.setattr(sc, "propose_trades",
                            lambda *a, **k: [(bars.index[-1], bars.index[-1], 0)])
        spec = {"symbols": {"SPY": _spec_entry()}}
        # loader returns bars already "closed" relative to the fixed now below
        return sc.Scanner(lambda s: bars, scorer=scorer, threshold=threshold,
                          state_path=tmp_path / "state.json", spec=spec), bars

    _NOW = datetime(2025, 6, 30, 0, 0, tzinfo=timezone.utc)   # long after bars

    def test_fires_then_dedups(self, tmp_path, monkeypatch):
        scanner, _ = self._scanner(tmp_path, monkeypatch)
        first = scanner.scan_once(now=self._NOW)
        assert len(first) == 1 and first[0].symbol == "SPY"
        second = scanner.scan_once(now=self._NOW)     # same bar → no re-alert
        assert second == []

    def test_state_file_written(self, tmp_path, monkeypatch):
        scanner, bars = self._scanner(tmp_path, monkeypatch)
        scanner.scan_once(now=self._NOW)
        import json
        state = json.loads((tmp_path / "state.json").read_text())
        assert state["SPY"] == bars.index[-1].isoformat()

    def test_scorer_below_threshold_filtered(self, tmp_path, monkeypatch):
        scanner, _ = self._scanner(tmp_path, monkeypatch,
                                   scorer=lambda sig, bars: 0.3, threshold=0.5)
        assert scanner.scan_once(now=self._NOW) == []

    def test_scorer_above_threshold_kept(self, tmp_path, monkeypatch):
        scanner, _ = self._scanner(tmp_path, monkeypatch,
                                   scorer=lambda sig, bars: 0.8, threshold=0.5)
        out = scanner.scan_once(now=self._NOW)
        assert len(out) == 1 and out[0].score == 0.8
