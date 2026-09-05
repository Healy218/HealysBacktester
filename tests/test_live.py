# tests/test_live.py
"""nn_meta.live: notifier, market-hours gating, closed-bar trimming, fresh-entry
detection, dedup, and the NN-scorer filter seam."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from nn_meta.live import scanner as sc
from nn_meta.live.notifier import (ConsoleNotifier, PushoverNotifier,
                                   TelegramNotifier, get_notifier)

_NOTIFY_VARS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "PUSHOVER_TOKEN", "PUSHOVER_USER")


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

    def test_telegram_success(self):
        s = _FakeSession(200)
        assert TelegramNotifier("tok", "42", session=s).send("m", "t") is True
        assert s.calls[0]["chat_id"] == "42" and "m" in s.calls[0]["text"]

    def test_telegram_http_error(self):
        assert TelegramNotifier("t", "c", session=_FakeSession(500)).send("m") is False

    def test_factory_console_when_no_creds(self, monkeypatch):
        for v in _NOTIFY_VARS:
            monkeypatch.delenv(v, raising=False)
        assert isinstance(get_notifier(), ConsoleNotifier)

    def test_factory_pushover_with_creds(self, monkeypatch):
        for v in _NOTIFY_VARS:
            monkeypatch.delenv(v, raising=False)
        monkeypatch.setenv("PUSHOVER_TOKEN", "x")
        monkeypatch.setenv("PUSHOVER_USER", "y")
        assert isinstance(get_notifier(), PushoverNotifier)
        assert isinstance(get_notifier(force_console=True), ConsoleNotifier)

    def test_factory_telegram_beats_pushover(self, monkeypatch):
        for v in _NOTIFY_VARS:
            monkeypatch.setenv(v, "x")
        assert isinstance(get_notifier(), TelegramNotifier)
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


def test_live_bar_loader_uses_cache_for_history_and_never_for_today(monkeypatch, tmp_path):
    """Regression (2026-09-05): the smart loader's cache key has no time
    component; a cached first pass made every later pass that day stale. Now:
    history (≤ yesterday) may use the cache; today is streamed or forced."""
    import pandas as pd
    from datetime import datetime, timezone
    from nn_meta.live import run_live
    calls = []
    def fake_smart(symbol, start, end, interval, cache_dir="data/cache", force_download=False):
        calls.append((start, end, force_download))
        day = pd.Timestamp(end)
        idx = pd.date_range(day.strftime("%Y-%m-%d") + " 13:30", periods=3, freq="15min")
        return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0}, index=idx)
    monkeypatch.setattr(run_live.vbt_data_loader, "load_price_data_smart", fake_smart)
    monkeypatch.setattr(run_live, "_feed_is_fresh", lambda now: False)
    now = datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc)
    out = run_live._bar_loader("SPY", now=now)
    assert [c[2] for c in calls] == [False, True]          # history cached, today forced
    assert calls[0][1] == "2026-09-03" and calls[1][0] == calls[1][1] == "2026-09-04"
    assert out.index[-1] == pd.Timestamp("2026-09-04 14:00")
    # with a fresh feed, today comes from the store and REST is not called for today
    from nn_meta.live.feeds.barstore import BarStore
    store = BarStore(tmp_path)
    store.append_1m("SPY", [{"timestamp": pd.Timestamp("2026-09-04 13:30") + pd.Timedelta(minutes=i),
                             "open": 5.0, "high": 5.0, "low": 5.0, "close": 5.0, "volume": 1.0} for i in range(30)])
    monkeypatch.setattr(run_live, "_feed_is_fresh", lambda now: True)
    monkeypatch.setattr("nn_meta.live.feeds.barstore.BarStore.__init__", lambda self, root=None: setattr(self, "root", tmp_path))
    calls.clear()
    out = run_live._bar_loader("SPY", now=now)
    assert [c[2] for c in calls] == [False]                # only the cached history call
    assert out.loc["2026-09-04 13:30", "Close"] == 5.0 and len(out.loc["2026-09-04"]) == 2


def test_heartbeat_reports_feeds_and_warns_when_stale(monkeypatch, tmp_path):
    import json
    from datetime import datetime, timedelta, timezone
    from nn_meta.live import heartbeat as hb
    stocks = tmp_path / "s.json"; options = tmp_path / "o.json"
    fresh = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    stocks.write_text(json.dumps({"ts": fresh, "bars": 900, "symbols": 443, "last_bar": "2026-09-08 14:29"}))
    options.write_text(json.dumps({"ts": stale, "quotes": 5, "contracts": 3}))
    monkeypatch.setattr(hb, "FEED_HEARTBEATS", {"stocks": stocks, "options": options})
    monkeypatch.setattr(hb, "EXPERT_LOGS", {})
    monkeypatch.setattr(hb, "is_rth", lambda *a, **k: True)
    monkeypatch.setattr(hb, "_today_lines", lambda: ([], "2026-09-08"))
    out = hb.build_message()
    msg = out[0] if isinstance(out, tuple) else out
    assert "feed stocks: 443 symbols" in msg and "feed options: 3 contracts" in msg
    assert "⚠️ feed options: heartbeat 20 min old" in msg
    assert "⚠️ feed stocks" not in msg
