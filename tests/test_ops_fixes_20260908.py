"""2026-09-08 server review fixes — one test class per item.

1 option feed idles instead of spinning · 2 refresh wrapper/worker override ·
3 quiet minutes tolerated when the stream was alive · 4 session-aware
staleness · 5 no-bars names are skips · 6 one top-five slot per idea and the
v3 tag · 7 quiet console filter and WARNING file handler · 8 heartbeat warns
on error counts, an idle options feed, stale surfaces and failed refreshes.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta.live.scanner import (NoBarsError, StaleBarsError, expected_last_closed_bar,
                                  require_recent_bars)
from nn_meta.live.feeds.barstore import BarStore, COLS, aggregate_15m
from nn_meta.live.alert_batches import Batches, EXPERTS, idea_of, select_top


def _bars(*stamps):
    return pd.DataFrame({"Close": [1.0] * len(stamps)}, index=pd.to_datetime(list(stamps)))


# ── 4: session-aware staleness ────────────────────────────────────────────────
@pytest.fixture
def labor_day_calendar(monkeypatch, tmp_path):
    """Captured calendar as deployed on the server: Fri 09-04 and Tue 09-08 are
    sessions, Mon 09-07 (Labor Day) is absent."""
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps({"coverage_start": "2026-09-01", "coverage_end": "2026-09-30",
                                "sessions": [{"date": "2026-09-04", "open": "09:30", "close": "16:00"},
                                             {"date": "2026-09-08", "open": "09:30", "close": "16:00"}]}))
    monkeypatch.setenv("NN_META_SESSION_CALENDAR", str(path))


class TestSessionAwareStaleness:
    def test_first_pass_after_holiday_keeps_fridays_bar(self, labor_day_calendar):
        # Tue 2026-09-08 09:36 ET (13:36 UTC), Labor Day Monday: today's first
        # bar has not closed, so Friday 15:45 ET is the newest closed bar.
        assert expected_last_closed_bar(pd.Timestamp("2026-09-08 13:36", tz="UTC")) \
            == pd.Timestamp("2026-09-04 19:45")
        bars = _bars("2026-09-04 19:45")
        assert require_recent_bars(bars, pd.Timestamp("2026-09-08 13:36")) is bars

    def test_still_stale_once_todays_first_bar_closed(self, labor_day_calendar):
        with pytest.raises(StaleBarsError, match="stale"):
            require_recent_bars(_bars("2026-09-04 19:45"), pd.Timestamp("2026-09-08 13:46"))

    def test_weekday_fallback_without_calendar_treats_monday_as_session(self, monkeypatch):
        # Isolate the fallback even on a host with a captured production calendar.
        monkeypatch.setattr("nn_meta.session_calendar.configured_calendar", lambda: None)
        assert expected_last_closed_bar(pd.Timestamp("2026-09-08 13:36", tz="UTC")) \
            == pd.Timestamp("2026-09-07 19:45")

    def test_one_interval_behind_is_tolerated_two_is_stale(self):
        now = pd.Timestamp("2026-09-08 19:00")           # 15:00 ET → the 14:45 ET (18:45) bar just closed
        assert expected_last_closed_bar(now) == pd.Timestamp("2026-09-08 18:45")
        require_recent_bars(_bars("2026-09-08 18:30"), now)
        with pytest.raises(StaleBarsError):
            require_recent_bars(_bars("2026-09-08 18:15"), now)

    def test_weekend_walks_back_to_friday(self):
        assert expected_last_closed_bar(pd.Timestamp("2026-09-06 15:00", tz="UTC")) \
            == pd.Timestamp("2026-09-04 19:45")

    def test_captured_calendar_early_close(self, monkeypatch, tmp_path):
        path = tmp_path / "calendar.json"
        path.write_text(json.dumps({"coverage_start": "2026-09-04", "coverage_end": "2026-09-08",
                                    "sessions": [{"date": "2026-09-04", "open": "09:30", "close": "13:00"}]}))
        monkeypatch.setenv("NN_META_SESSION_CALENDAR", str(path))
        # Tue 09:36 ET after a Monday holiday and a Friday 13:00 early close
        assert expected_last_closed_bar(pd.Timestamp("2026-09-08 13:36", tz="UTC")) \
            == pd.Timestamp("2026-09-04 16:45")
        require_recent_bars(_bars("2026-09-04 16:45"), pd.Timestamp("2026-09-08 13:36"))

    def test_empty_frame_is_no_bars_not_stale(self):
        with pytest.raises(NoBarsError, match="no closed market bars"):
            require_recent_bars(pd.DataFrame(), pd.Timestamp("2026-09-08 14:00"))


# ── 5: delisted names are skips ───────────────────────────────────────────────
class TestNoBarsSkip:
    def test_v4_scan_counts_skip_not_error(self, tmp_path, monkeypatch):
        from nn_meta.live import v4_scan
        calls = []
        def loader(sym):
            calls.append(sym)
            return pd.DataFrame(columns=COLS)          # nothing at all → delisted
        bundle = SimpleNamespace(threshold=0.5, mode="p", family="gbt",
                                 score=lambda b: None, ev=lambda b: None)
        summary = v4_scan.scan_pass(bundle=bundle, spec={"symbols": {"WBA": {}, "X": {}}},
                                    surface=pd.DataFrame(), bar_loader=loader,
                                    notifier=SimpleNamespace(send=lambda *a, **k: True),
                                    now=datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc),
                                    state_dir=tmp_path, workers=1)
        assert calls == ["WBA", "X"]
        assert summary["error_count"] == 0 and summary["skipped"] == 2 and summary["scanned"] == 0
        # next pass: the memo keeps the loader off both names; a week later they are rechecked
        calls.clear()
        kw = dict(bundle=bundle, spec={"symbols": {"WBA": {}, "X": {}}}, surface=pd.DataFrame(),
                  bar_loader=loader, notifier=SimpleNamespace(send=lambda *a, **k: True),
                  state_dir=tmp_path, workers=1)
        s2 = v4_scan.scan_pass(now=datetime(2026, 9, 8, 14, 15, tzinfo=timezone.utc), **kw)
        assert calls == [] and s2["skipped"] == 2 and s2["error_count"] == 0
        s3 = v4_scan.scan_pass(now=datetime(2026, 9, 16, 14, 15, tzinfo=timezone.utc), **kw)
        assert calls == ["WBA", "X"] and s3["skipped"] == 2

    def test_legacy_scanner_memo(self, tmp_path):
        from nn_meta.live.scanner import NoBarsMemo
        m = NoBarsMemo(tmp_path / "memo.json")
        m.mark("X", datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)); m.save()
        m2 = NoBarsMemo(tmp_path / "memo.json")
        assert m2.active(pd.Timestamp("2026-09-10 14:00")) == {"X"}
        assert m2.active(pd.Timestamp("2026-09-16 14:00")) == set()
        (tmp_path / "memo.json").write_text("garbage")
        assert NoBarsMemo(tmp_path / "memo.json").active(pd.Timestamp("2026-09-10")) == set()


# ── 3: quiet minutes vs stream gaps ───────────────────────────────────────────
def _m1(start="2026-09-04 13:30", n=15, drop=()):
    idx = pd.date_range(start, periods=n, freq="1min")
    idx = idx.drop([pd.Timestamp(d) for d in drop])
    return pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10.0}, index=idx)


class TestAliveMinuteGaps:
    NOW = pd.Timestamp("2026-09-04 13:46")

    def test_strict_without_reference(self):
        with pytest.raises(ValueError, match="Incomplete"):
            aggregate_15m(_m1(drop=["2026-09-04 13:35"]), now=self.NOW)

    def test_gap_accepted_when_reference_was_alive(self):
        alive = set(pd.date_range("2026-09-04 13:30", periods=15, freq="1min"))
        out = aggregate_15m(_m1(drop=["2026-09-04 13:35", "2026-09-04 13:43"]), now=self.NOW,
                            alive_minutes=alive)
        assert list(out.index) == [pd.Timestamp("2026-09-04 13:30")]
        assert out.iloc[0].Volume == 130.0                 # 13 traded minutes summed

    def test_gap_rejected_when_reference_missed_it_too(self):
        alive = set(pd.date_range("2026-09-04 13:30", periods=15, freq="1min")) - {pd.Timestamp("2026-09-04 13:35")}
        with pytest.raises(ValueError, match="stream gap unproven"):
            aggregate_15m(_m1(drop=["2026-09-04 13:35"]), now=self.NOW, alive_minutes=alive)

    def test_store_uses_reference_symbols(self, tmp_path):
        s = BarStore(tmp_path)
        s.append_1m("SPY", [{"timestamp": t, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
                            for t in _m1().index])
        s.append_1m("IEF", [{"timestamp": t, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
                            for t in _m1(drop=["2026-09-04 13:41"]).index])
        assert len(s.read_15m("IEF", now=self.NOW)) == 1
        with pytest.raises(ValueError):
            s.read_15m("IEF", now=self.NOW, reference=None)
        # the reference's own gap is never excused
        s2 = BarStore(tmp_path / "b")
        s2.append_1m("SPY", [{"timestamp": t, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
                             for t in _m1(drop=["2026-09-04 13:41"]).index])
        with pytest.raises(ValueError):
            s2.read_15m("SPY", now=self.NOW)


# ── 6: one slot per idea, tagged titles ───────────────────────────────────────
class _Notify:
    def __init__(self): self.sent = []
    def send(self, message, title=""): self.sent.append(title); return True


def _entry(i, symbol, side, expert="v5", batch=900, score=None):
    return {"title": f"[{expert}] {symbol} {side}", "message": "m", "probability": score or i / 100,
            "expert": expert, "alert_cycle": batch, "symbol": symbol, "side": side}


class TestOneSlotPerIdea:
    def test_duplicate_idea_yields_its_slot(self, tmp_path):
        q = Batches(tmp_path / "q.db"); n = _Notify()
        entries = [_entry(90, "SIL", "BUY PUT"), _entry(89, "SIL", "BUY PUT"), _entry(88, "AZO", "BUY CALL"),
                   _entry(87, "AZO", "BUY CALL"), _entry(86, "FANG", "BUY PUT"), _entry(85, "HYG", "BUY PUT"),
                   _entry(84, "HYG", "BUY PUT", expert="v31"), _entry(83, "ET", "BUY CALL"), _entry(82, "KO", "BUY PUT"),
                   _entry(81, "SIL", "BUY CALL")]                    # other side = a different idea
        for i, e in enumerate(entries):
            assert q.enqueue(dict(e, probability=0.9 - i / 100), f"k{i}", now=1000)
        for expert in EXPERTS: q.complete(expert, 900)
        assert q.dispatch(n, now=1001) == 5
        assert n.sent == ["[v5] SIL BUY PUT", "[v5] AZO BUY CALL", "[v5] FANG BUY PUT",
                          "[v5] HYG BUY PUT", "[v5] ET BUY CALL"]
        with q.connect() as db:
            rows = {r["key"]: r["status"] for r in db.execute("SELECT key,status FROM candidates")}
        assert rows["k1"] == "suppressed_rank" and rows["k6"] == "suppressed_rank"   # dupes listed in the remainder

    def test_legacy_titles_parse_and_unknown_never_dedupes(self):
        assert idea_of({"title": "[v31] SMCI BUY CALL"}) == ("SMCI", "BUY CALL")
        assert idea_of({"title": "ORCL BUY PUT"}) == ("ORCL", "BUY PUT")
        assert idea_of({"title": "7"}) is None
        rows = [{"key": "a", "symbol": None, "side": None}, {"key": "b", "symbol": None, "side": None}]
        assert select_top(rows, top_n=5) == ["a", "b"]

    def test_existing_queue_is_migrated(self, tmp_path):
        import sqlite3
        db = sqlite3.connect(tmp_path / "old.db")
        db.executescript("CREATE TABLE candidates (key TEXT PRIMARY KEY, batch INTEGER, expert TEXT, score REAL, title TEXT, message TEXT, status TEXT, summary TEXT);")
        db.commit(); db.close()
        q = Batches(tmp_path / "old.db")
        assert q.enqueue(_entry(60, "KO", "BUY PUT"), "k", now=1000)
        with q.connect() as c:
            assert tuple(c.execute("SELECT symbol, side FROM candidates").fetchone()) == ("KO", "BUY PUT")

    def test_v3_title_is_tagged(self, monkeypatch):
        from nn_meta import config
        from nn_meta.live import scanner as sc
        monkeypatch.setattr(config, "POOL", "v3")
        sig = sc.Signal(symbol="ORCL", strategy="rsi", direction=0, right="C",
                        bar_ts=pd.Timestamp("2026-09-08 19:30"), dte=30, spot=250.0,
                        param_label="entry=30", score=0.62)
        title, msg = sc.format_alert(sig)
        assert title == "[v3] ORCL BUY CALL" and "paper" not in msg


# ── 7: logging volume ─────────────────────────────────────────────────────────
class TestQuietLogging:
    def test_quiet_filter_keeps_live_lines_and_warnings(self):
        from utils.logging_utils import QuietScanFilter
        f = QuietScanFilter()
        mk = lambda lvl, msg: logging.LogRecord("backtester", lvl, "", 0, msg, None, None)
        assert f.filter(mk(logging.INFO, "[v4-scan] SQQQ/volume: filtered (best ev 0.045)"))
        assert f.filter(mk(logging.INFO, "[live] GS: stream unavailable; using REST"))
        assert f.filter(mk(logging.WARNING, "Running vectorbt Portfolio.from_signals simulation..."))
        assert not f.filter(mk(logging.INFO, "Running vectorbt Portfolio.from_signals simulation..."))
        assert not f.filter(mk(logging.INFO, "[vbt-smart] Cache hit: data/cache/LQD_15m.csv"))

    def test_file_handler_defaults_to_warning(self, tmp_path, monkeypatch):
        import importlib
        import utils.logging_utils as lu
        monkeypatch.delenv("BACKTESTER_FILE_LOG_LEVEL", raising=False)
        lu = importlib.reload(lu)
        logger = logging.getLogger("backtester")
        saved = list(logger.handlers); logger.handlers.clear()
        try:
            lg = lu.setup_logging(log_file=str(tmp_path / "bt.log"))
            lg.info("chatter"); lg.error("[live] AAPL: scan error: boom")
            for h in lg.handlers: h.flush()
            text = (tmp_path / "bt.log").read_text()
            assert "chatter" not in text and "- ERROR - [live] AAPL" in text
        finally:
            for h in logger.handlers:
                h.close()
            logger.handlers[:] = saved

    def test_cron_rewrite_is_idempotent(self):
        from scripts.configure_cron import updated_cron, SCAN_ENV
        repo = "/home/mrhea/HealysBacktester"
        original = "\n".join([
            "3,18,33,48 * * * * cd /home/mrhea/HealysBacktester && NN_META_ALERT_TOP_N=5 NN_META_POOL=v3 ./venv/bin/python -m nn_meta.live.run_live --once --nn --workers 1 >> logs/live_cron.log 2>&1",
            "0 17 * * * cd /home/mrhea/HealysBacktester && ./venv/bin/python -m nn_meta.live.heartbeat >> logs/heartbeat_cron.log 2>&1",
            "0 14 * * 0 cd /home/mrhea/HealysBacktester && NN_META_POOL=v5 ./venv/bin/python -m nn_meta.download_universe --bars-and-surface-only --refresh-recent-days 10 >> logs/surface_refresh_v5.log 2>&1 && NN_META_POOL=v5 ./venv/bin/python -m nn_meta.build_surface >> logs/surface_refresh_v5.log 2>&1",
            "0 13 * * 0 cd /home/mrhea/HealysBacktester && NN_META_POOL=v5 ./venv/bin/python -m nn_meta.download_universe --universe-only --live-horizon 120 >> logs/universe_refresh_v5.log 2>&1",
            "# DISABLED 2026-09-08 (option feed has no subscribers; re-enable after watch-list wire-up)",
            "#@reboot cd /home/mrhea/HealysBacktester && sleep 25 && NN_META_POOL=v31 nohup ./venv/bin/python -m nn_meta.live.feeds.option_stream >> logs/feeds_options.log 2>&1 &",
            "#*/5 * * * * cd /home/mrhea/HealysBacktester && pgrep -f \"[f]eeds.option_stream\" >/dev/null || (NN_META_POOL=v31 nohup ./venv/bin/python -m nn_meta.live.feeds.option_stream >> logs/feeds_options.log 2>&1 &)",
            "* * * * * cd /home/mrhea/HealysBacktester && NN_META_ALERT_TOP_N=5 ./venv/bin/python -m nn_meta.live.alert_batches >> logs/alert_batches.log 2>&1",
            "*/5 * * * * cd /home/mrhea/HealysBacktester && pgrep -f \"[f]eeds.stock_stream\" >/dev/null || (NN_META_POOL=v31 nohup ./venv/bin/python -m nn_meta.live.feeds.stock_stream >> logs/feeds_stock.log 2>&1 &)",
        ]) + "\n"
        once = updated_cron(original, repo)
        assert updated_cron(once, repo) == once
        lines = once.splitlines()
        assert lines[0].startswith(f"3,18,33,48 * * * * cd {repo} && {SCAN_ENV} NN_META_ALERT_TOP_N=5")
        assert "heartbeat" in lines[1] and SCAN_ENV not in lines[1]
        assert lines[2] == f"0 14 * * 0 cd {repo} && ./scripts/run_refresh.sh v5 >> logs/surface_refresh_v5.log 2>&1"
        assert "--universe-only" in lines[3]
        assert lines[5].startswith("#@reboot") and lines[6].startswith("#*/5")
        assert any(ln.startswith("7 4 * * * ") and "rotate_logs.sh" in ln for ln in lines)
        # watchdog no longer matches its own sh -c line (which contains "-m nn_meta.live.feeds.stock_stream")
        assert lines[8].startswith('*/5 * * * * cd /home/mrhea/HealysBacktester && pgrep -f "feeds\\.stock_stream$" >/dev/null || (')
        import re, subprocess
        pat = re.search(r'pgrep -f "([^"]+)"', lines[8]).group(1)
        assert re.search(pat, lines[8]) is None and re.search(pat, "./venv/bin/python -m nn_meta.live.feeds.stock_stream")
        enabled = updated_cron(once, repo, enable_option_feed=True)
        assert "\n@reboot cd" in enabled and "\n*/5 * * * * cd" in enabled and "DISABLED 2026-09-08" not in enabled
        assert updated_cron(enabled, repo, enable_option_feed=True) == enabled


# ── 8: heartbeat escalations ──────────────────────────────────────────────────
class TestHeartbeatEscalations:
    @pytest.fixture
    def hb(self, tmp_path, monkeypatch):
        from nn_meta.live import heartbeat
        ns = SimpleNamespace(bl=tmp_path / "backtester.log", st=tmp_path / "state.json",
                             feeds=tmp_path / "feeds", surf=tmp_path / "surf", status=tmp_path / "status")
        monkeypatch.setattr(heartbeat, "BACKTESTER_LOG", ns.bl)
        monkeypatch.setattr(heartbeat, "STATE", ns.st)
        (tmp_path / "live_cron.log").write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "EXPERT_LOGS", {"v3": tmp_path / "live_cron.log"})
        monkeypatch.setattr(heartbeat, "FEED_HEARTBEATS", {"stocks": ns.feeds / "s.json", "options": ns.feeds / "o.json"})
        monkeypatch.setattr(heartbeat, "SURFACE_FILES", {"v5": ns.surf / "v5.parquet"})
        monkeypatch.setattr(heartbeat, "REFRESH_STATUS_DIR", ns.status)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        ns.mod = heartbeat
        return ns

    def _today(self, *msgs):
        d = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
        return "\n".join(f"{d} 15:00,000 - backtester - {m}" for m in msgs)

    def test_quiet_day_is_healthy(self, hb):
        hb.bl.write_text(self._today("INFO - fine"))
        msg, _ = hb.mod.build_message()
        assert msg.startswith("🩺") and "surfaces: v5 —" in msg

    def test_many_errors_warn(self, hb):
        hb.bl.write_text(self._today(*(["ERROR - [v4-scan] X: scan error: boom"] * 60)))
        msg, _ = hb.mod.build_message()
        assert msg.startswith("⚠️") and "60 scanner errors today" in msg

    def test_idle_options_feed_warns_only_in_rth(self, hb, monkeypatch):
        hb.feeds.mkdir()
        (hb.feeds / "o.json").write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                                     "quotes": 0, "contracts": 0}))
        msg, _ = hb.mod.build_message()
        assert "0 contracts subscribed" in msg and msg.startswith("⚠️")
        monkeypatch.setattr(hb.mod, "is_rth", lambda: False)
        assert hb.mod.build_message()[0].startswith("🩺")

    def test_stale_surface_and_failed_refresh_warn(self, hb):
        hb.surf.mkdir(); f = hb.surf / "v5.parquet"; f.write_bytes(b"x")
        old = time.time() - 14 * 86400
        os.utime(f, (old, old))
        msg, _ = hb.mod.build_message()
        assert "v5: IV surface is 14 days old" in msg and "surfaces: v5 14d" in msg
        os.utime(f, None)
        hb.status.mkdir()
        (hb.status / "v5.json").write_text(json.dumps({"exit_code": 137, "finished": "2026-09-06T16:05:00+00:00",
                                                       "log": "logs/surface_refresh_v5.log"}))
        msg, _ = hb.mod.build_message()
        assert "last surface refresh exited 137" in msg and msg.startswith("⚠️")
        (hb.status / "v5.json").write_text(json.dumps({"exit_code": 0}))
        assert hb.mod.build_message()[0].startswith("🩺")


# ── 1: option feed gate + contract resolution ─────────────────────────────────
class TestOptionFeed:
    def test_stream_idles_until_watch_list_has_contracts(self, tmp_path, monkeypatch):
        from nn_meta.live.feeds import option_stream as os_
        monkeypatch.setenv("ALPACA_API_KEY", "k"); monkeypatch.setenv("ALPACA_API_SECRET", "s")
        monkeypatch.setattr(os_, "WATCH", tmp_path / "watch.json")
        monkeypatch.setattr(os_, "HEARTBEAT", tmp_path / "hb.json")
        monkeypatch.setattr(os_, "IDLE_POLL_S", 0.01)
        started = []
        class FakeStream:
            def __init__(self, *a, **k): pass
            def subscribe_quotes(self, handler, *syms): started.append(("sub", syms))
            def unsubscribe_quotes(self, *syms): pass
            async def _run_forever(self):
                started.append("run"); await asyncio.sleep(3600)
            async def close(self): pass
        import types, sys
        fake_live = types.ModuleType("alpaca.data.live"); fake_live.OptionDataStream = FakeStream
        fake_enums = types.ModuleType("alpaca.data.enums"); fake_enums.OptionsFeed = SimpleNamespace(OPRA="opra")
        monkeypatch.setitem(sys.modules, "alpaca.data.live", fake_live)
        monkeypatch.setitem(sys.modules, "alpaca.data.enums", fake_enums)
        store = SimpleNamespace(update=lambda *a, **k: None, flush=lambda: 0)
        # empty watch list: idles for the whole run window, never starts the ws loop
        asyncio.run(os_._serve(store, None, run_seconds=0.05))
        assert "run" not in started
        assert json.loads((tmp_path / "hb.json").read_text())["state"] == "idle"
        # a registered contract ends the idle wait and starts the loop
        os_.add_to_watch(["SPY260918C00650000"], tmp_path / "watch.json")
        async def run_briefly():
            task = asyncio.ensure_future(os_._serve(store, None, run_seconds=None))
            await asyncio.sleep(0.1); task.cancel()
            try: await task
            except asyncio.CancelledError: pass
        asyncio.run(run_briefly())
        assert "run" in started and ("sub", ("SPY260918C00650000",)) in started

    def test_resolve_occ_prefers_nearest_expiry_then_strike(self):
        from nn_meta.live.feeds.contracts import resolve_occ
        listing = pd.DataFrame({
            "ticker": ["O:AAPL261016C00250000", "O:AAPL261016C00255000", "O:AAPL261120C00250000",
                       "O:AAPL261016P00250000", "O:AAPL260911C00250000"],
            "underlying": ["AAPL"] * 5, "strike": [250.0, 255.0, 250.0, 250.0, 250.0],
            "expiration": pd.to_datetime(["2026-10-16", "2026-10-16", "2026-11-20", "2026-10-16", "2026-09-11"]),
            "type": ["c", "c", "c", "p", "c"]})
        now = datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc)
        assert resolve_occ("AAPL", "C", 253.9, 45, now, listing=listing) == "AAPL261016C00255000"
        assert resolve_occ("AAPL", "P", 100.0, 30, now, listing=listing) == "AAPL261016P00250000"
        assert resolve_occ("MSFT", "C", 1.0, 30, now, listing=listing) is None
        assert resolve_occ("AAPL", "C", 250.0, 1, now, listing=listing) == "AAPL260911C00250000"

    def test_alert_path_registers_contract(self, tmp_path, monkeypatch):
        from nn_meta.live import scanner as sc
        from nn_meta.live.feeds import option_stream as os_, contracts
        monkeypatch.setattr(os_, "WATCH", tmp_path / "watch.json")
        monkeypatch.setattr(contracts, "load_listing", lambda path=None: pd.DataFrame({
            "ticker": ["O:KO261009P00087000"], "underlying": ["KO"], "strike": [87.0],
            "expiration": pd.to_datetime(["2026-10-09"]), "type": ["p"]}))
        occ = sc.register_alert_contract("KO", "P", 87.4, 30, datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc))
        assert occ == "KO261009P00087000" and os_.read_watch(tmp_path / "watch.json") == [occ]
        monkeypatch.setattr(contracts, "load_listing", lambda path=None: None)
        assert sc.register_alert_contract("KO", "P", 87.4, 30, None) is None    # never raises


# ── follow-up: surface loader and refresh watcher ─────────────────────────────
class TestSurfaceLoaderAndWatcher:
    def test_indexed_join_matches_merge_path(self, tmp_path, monkeypatch):
        from nn_meta import config
        from nn_meta import build_surface as bs
        rng = pd.date_range("2026-08-03", periods=12, freq="B")
        meta = pd.DataFrame({"ticker": [f"T{i}" for i in range(6)] + ["T1"],   # one duplicate universe row
                             "underlying": ["AAA"] * 3 + ["BBB"] * 3 + ["AAA"],
                             "strike": [10, 11, 12, 20, 21, 22, 11], "type": ["call", "put"] * 3 + ["put"],
                             "expiration": ["2026-08-21"] * 3 + ["2026-09-18"] * 3 + ["2026-08-21"]})
        (tmp_path / "bars").mkdir()
        meta.to_parquet(tmp_path / "universe.parquet")
        rows = []
        for i, t in enumerate([f"T{i}" for i in range(6)] + ["ZZ"]):     # ZZ is not in the universe
            for d in rng:
                rows.append({"ticker": t, "date": d, "close": 0.02 + i * 0.5, "volume": 10})
        bars = pd.DataFrame(rows)
        for k, chunk in enumerate([bars.iloc[:30], bars.iloc[30:60], bars.iloc[60:], bars.iloc[:5]]):  # overlap → dedupe
            chunk.to_parquet(tmp_path / "bars" / f"bars_part_{k:04d}.parquet")
        monkeypatch.setattr(config, "UNIVERSE_PARQUET", tmp_path / "universe.parquet")
        monkeypatch.setattr(config, "BARS_DAILY_DIR", tmp_path / "bars")
        monkeypatch.setattr(config, "DTE_MAX", 45)
        monkeypatch.setattr(config, "MIN_PREMIUM", 0.05)
        got = bs.load_daily_bars()
        # reference = the pre-2026-09-08 merge path
        m = pd.read_parquet(tmp_path / "universe.parquet"); m["expiration"] = pd.to_datetime(m["expiration"])
        ref = []
        for p in sorted((tmp_path / "bars").glob("*.parquet")):
            b = pd.read_parquet(p, columns=["ticker", "date", "close", "volume"]).merge(m, on="ticker", how="inner")
            dte = (b["expiration"] - b["date"]).dt.days
            ref.append(b[(dte >= 1) & (dte <= 45) & (b["close"] >= 0.05)])
        ref = pd.concat(ref, ignore_index=True).drop_duplicates(["ticker", "date"])
        key = ["ticker", "date"]
        assert len(got) == len(ref) and "ZZ" not in set(got["ticker"]) and "T0" not in set(got["ticker"])
        pd.testing.assert_frame_equal(got.sort_values(key).reset_index(drop=True)[sorted(got.columns)],
                                      ref.sort_values(key).reset_index(drop=True)[sorted(got.columns)])

    def test_watcher_report_and_done_detection(self, tmp_path, monkeypatch):
        from scripts import watch_refresh as wr
        base = {"pool": "v5", "surface_age_h": 30 * 24.0, "tail": "  150000/219108 (56/s, ETA 0.3h)",
                "now": "2026-09-09T01:00:00+00:00",
                "status": {"started": "2026-09-08T20:40:22Z", "workers": "6", "step": "download", "exit_code": -1}}
        running = dict(base, processes=[{"pid": 1, "step": "build_surface", "elapsed_s": 7300, "rss_mb": 3100}])
        msg, done = wr.format_report(running)
        assert not done and "running · build_surface 2h01m · 3100 MB RSS" in msg and "30.0 d old" in msg
        finished = dict(base, processes=[], status=dict(base["status"], exit_code=0, step="build_surface",
                                                        finished="2026-09-09T01:30:00+00:00"), surface_age_h=0.1)
        msg, done = wr.format_report(finished)
        assert done and "FINISHED OK" in msg and "6 min old" in msg
        failed = dict(base, processes=[], status=dict(base["status"], exit_code=137))
        assert wr.format_report(failed)[1] and "FAILED" in wr.format_report(failed)[0]
        vanished = dict(base, processes=[])
        assert wr.format_report(vanished)[1] and "killed?" in wr.format_report(vanished)[0]
        # gather() reads the real files under a fake root
        (tmp_path / "logs" / "refresh_status").mkdir(parents=True)
        (tmp_path / "logs" / "refresh_status" / "v5.json").write_text(json.dumps(base["status"]))
        (tmp_path / "logs" / "surface_refresh_v5.log").write_text("a\n  1/2 parts\n\n")
        monkeypatch.setenv("NN_META_POOL", "v5")
        info = wr.gather("v5", root=tmp_path)
        assert info["status"]["workers"] == "6" and info["tail"] == "1/2 parts" and isinstance(info["processes"], list)

    def test_streaming_surface_equals_in_memory_surface(self, tmp_path, monkeypatch):
        from nn_meta import config
        from nn_meta import build_surface as bs
        rng = pd.date_range("2026-06-01", periods=40, freq="B")
        und = pd.concat([pd.DataFrame({"underlying": u, "date": rng, "open": px, "high": px * 1.01,
                                       "low": px * 0.99, "close": px * (1 + 0.001 * np.arange(40)),
                                       "volume": 1e6, "vwap": px, "transactions": 100})
                         for u, px in (("AAA", 100.0), ("BBB", 50.0))], ignore_index=True)
        tickers = []
        for u, px in (("AAA", 100.0), ("BBB", 50.0)):
            for exp in ("2026-07-17", "2026-08-21"):
                for k in np.linspace(px * 0.97, px * 1.03, 13):
                    for t in ("call", "put"):
                        tickers.append({"ticker": f"{u}{exp}{t[0]}{k:.2f}", "underlying": u, "strike": round(k, 2),
                                        "expiration": exp, "type": t})
        meta = pd.DataFrame(tickers)
        rs = np.random.default_rng(0)
        rows = []
        for tk in meta.itertuples():
            for d in rng:
                rows.append({"ticker": tk.ticker, "date": d, "close": float(rs.uniform(0.2, 5.0)),
                             "volume": int(rs.integers(0, 500))})
        bars = pd.DataFrame(rows)
        (tmp_path / "bars").mkdir()
        # compacted layout: no ticker spans two parts; one part carries an exact duplicate row
        for k, (_, grp) in enumerate(bars.groupby(bars["ticker"].str[:3])):
            grp = pd.concat([grp, grp.iloc[:3]]) if k == 0 else grp
            grp.to_parquet(tmp_path / "bars" / f"bars_part_{k:04d}.parquet", index=False)
        meta.to_parquet(tmp_path / "universe.parquet")
        monkeypatch.setattr(config, "UNIVERSE_PARQUET", tmp_path / "universe.parquet")
        monkeypatch.setattr(config, "BARS_DAILY_DIR", tmp_path / "bars")
        monkeypatch.setattr(config, "DTE_MAX", 60)
        monkeypatch.setattr(config, "MIN_PREMIUM", 0.05)
        ref = bs.build_surface(bs.load_daily_bars(), und).reset_index(drop=True)
        got = bs.build_surface_streaming(und).reset_index(drop=True)
        assert ref["atm_iv_near"].notna().any() and ref["pc_ratio"].notna().any()
        pd.testing.assert_frame_equal(got, ref)


class TestOptionStreamRunningRefresh:
    def test_refresh_on_running_stream_never_calls_blocking_subscribe(self, tmp_path, monkeypatch):
        """alpaca-py's subscribe_quotes blocks on .result() once running — from
        inside the loop that is a deadlock. The refresh must go async."""
        from nn_meta.live.feeds import option_stream as os_
        monkeypatch.setenv("ALPACA_API_KEY", "k"); monkeypatch.setenv("ALPACA_API_SECRET", "s")
        monkeypatch.setattr(os_, "WATCH", tmp_path / "watch.json")
        monkeypatch.setattr(os_, "HEARTBEAT", tmp_path / "hb.json")
        monkeypatch.setattr(os_, "IDLE_POLL_S", 0.01); monkeypatch.setattr(os_, "REFRESH_S", 0.05)
        monkeypatch.setattr(os_, "FLUSH_S", 0.02); monkeypatch.setattr(os_, "LOOP_TICK_S", 0.01)
        events = []
        class FakeStream:
            def __init__(self, *a, **k):
                self._running = False; self._handlers = {"quotes": {}}
            def subscribe_quotes(self, handler, *syms):
                if self._running:
                    events.append("BLOCKING-SUBSCRIBE"); raise AssertionError("would deadlock")
                for s_ in syms: self._handlers["quotes"][s_] = handler
                events.append(("sub", syms))
            def unsubscribe_quotes(self, *syms):
                if self._running: events.append("BLOCKING-UNSUBSCRIBE"); raise AssertionError("would deadlock")
            async def _send_subscribe_msg(self): events.append(("msg-sub", tuple(sorted(self._handlers["quotes"]))))
            async def _send_unsubscribe_msg(self, channel, syms): events.append(("msg-unsub", channel, tuple(syms)))
            async def _run_forever(self):
                self._running = True; events.append("run"); await asyncio.sleep(3600)
            async def close(self): pass
        import types, sys
        fake_live = types.ModuleType("alpaca.data.live"); fake_live.OptionDataStream = FakeStream
        fake_enums = types.ModuleType("alpaca.data.enums"); fake_enums.OptionsFeed = SimpleNamespace(OPRA="opra")
        monkeypatch.setitem(sys.modules, "alpaca.data.live", fake_live)
        monkeypatch.setitem(sys.modules, "alpaca.data.enums", fake_enums)
        store = SimpleNamespace(update=lambda *a, **k: None, flush=lambda: 0)
        os_.add_to_watch(["SPY260918C00650000"], tmp_path / "watch.json")
        async def scenario():
            task = asyncio.ensure_future(os_._serve(store, None, run_seconds=None))
            await asyncio.sleep(0.1)                       # running with one contract
            os_.add_to_watch(["QQQ260918P00500000"], tmp_path / "watch.json")
            await asyncio.sleep(0.2)                       # a refresh has fired
            (tmp_path / "watch.json").write_text(json.dumps({"contracts": ["QQQ260918P00500000"]}))
            await asyncio.sleep(0.2)                       # SPY dropped
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
        asyncio.run(scenario())
        assert "BLOCKING-SUBSCRIBE" not in events and "BLOCKING-UNSUBSCRIBE" not in events
        assert ("sub", ("SPY260918C00650000",)) in events and "run" in events
        assert ("msg-sub", ("QQQ260918P00500000", "SPY260918C00650000")) in events
        assert ("msg-unsub", "quotes", ("SPY260918C00650000",)) in events
        hb = json.loads((tmp_path / "hb.json").read_text())
        assert hb["contracts"] == 1 and "state" not in hb    # streaming, one contract left

    def test_stall_guard_detects_silent_loop(self):
        from nn_meta.live.feeds.option_stream import loop_stalled
        assert not loop_stalled(now=1000.0, last_tick=950.0)
        assert loop_stalled(now=1000.0, last_tick=800.0)



# ── 2026-09-09: real contract + live quote in the alert (user: "option 1") ──
_SNAPSHOT = {"status": "OK", "results": {
    "details": {"contract_type": "call", "expiration_date": "2026-10-09", "strike_price": 11.5,
                "ticker": "O:MARA261009C00011500"},
    "greeks": {"delta": 0.5872747, "gamma": 0.136, "theta": -0.019, "vega": 0.013},
    "implied_volatility": 0.8539426,
    "last_quote": {"ask": 1.31, "ask_size": 86, "bid": 1.26, "bid_size": 88,
                   "last_updated": 1788974565824497987, "midpoint": 1.285, "timeframe": "REAL-TIME"}}}


class TestContractAndQuoteInAlerts:
    def test_massive_snapshot_parses_nbbo_and_greeks(self, monkeypatch):
        from options.data.massive_provider import MassiveProvider
        monkeypatch.setenv("MASSIVE_API_KEY", "k")
        p = MassiveProvider()
        seen = []
        monkeypatch.setattr(p, "_get", lambda path, params: (seen.append(path), _SNAPSHOT)[1])
        q = p.get_contract_snapshot("MARA261009C00011500")
        assert seen == ["/v3/snapshot/options/MARA/O:MARA261009C00011500"]
        assert q["bid"] == 1.26 and q["ask"] == 1.31 and q["bid_size"] == 88 and q["source"] == "rest"
        assert abs(q["delta"] - 0.587) < 0.01 and abs(q["iv"] - 0.854) < 0.01
        assert q["ts"].startswith("2026-09-09T17:")
        monkeypatch.setattr(p, "_get", lambda path, params: {"status": "OK", "results": {"details": {}}})
        assert p.get_contract_snapshot("MARA261009C00011500") is None

    def test_live_quote_prefers_fresh_stream_then_rest(self, tmp_path, monkeypatch):
        from nn_meta.live.feeds import quotes as qm
        from nn_meta.live.feeds.quotestore import QuoteStore
        store = QuoteStore(tmp_path / "q.json")
        store.update("MARA261009C00011500", bid=1.20, ask=1.24, bid_size=5, ask_size=7,
                     ts=datetime.now(timezone.utc)); store.flush()
        calls = []
        class FakeMassive:
            def __init__(self, *a, **k): pass
            def get_contract_snapshot(self, occ): calls.append(occ); return {"bid": 1.26, "ask": 1.31, "ts": datetime.now(timezone.utc).isoformat(), "source": "rest"}
        import types, sys
        fake = types.ModuleType("options.data.massive_provider"); fake.MassiveProvider = FakeMassive
        monkeypatch.setitem(sys.modules, "options.data.massive_provider", fake)
        q = qm.live_quote("MARA261009C00011500", store_path=tmp_path / "q.json")
        assert q["source"] == "stream" and q["bid"] == 1.20 and calls == []
        q = qm.live_quote("QQQ260918P00500000", store_path=tmp_path / "q.json")      # not streamed yet
        assert q["source"] == "rest" and calls == ["QQQ260918P00500000"]
        assert qm.live_quote("SPY260918C00650000", store_path=tmp_path / "q.json", allow_rest=False) is None
        # a stale streamed quote is not "live": fall through to REST
        store.update("AAPL261023P00315000", bid=1, ask=2, ts=datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)); store.flush()
        assert qm.live_quote("AAPL261023P00315000", store_path=tmp_path / "q.json")["source"] == "rest"

    def test_alert_lines_format(self):
        from nn_meta.live.feeds.quotes import contract_lines, format_contract, format_quote_line
        assert format_contract("MARA261009C00011500") == "MARA 2026-10-09 $11.50 CALL (MARA261009C00011500)"
        assert format_contract("ASHR261023P00034000") == "ASHR 2026-10-23 $34 PUT (ASHR261023P00034000)"
        now = datetime(2026, 9, 9, 17, 22, 48, tzinfo=timezone.utc)
        q = {"bid": 1.26, "ask": 1.31, "bid_size": 99, "ask_size": 31, "ts": "2026-09-09T17:22:45+00:00",
             "delta": 0.587, "iv": 0.854, "source": "rest"}
        assert format_quote_line(q, now) == "quote: bid 1.26 / ask 1.31 · mid 1.29 · spread 3.9% · 99x31 · 3s old · Δ 0.59 · IV 85% · rest"
        assert format_quote_line(None) == "quote: unavailable"
        block = contract_lines("MARA261009C00011500", None, "~ATM C near $11.73")
        assert block == "contract: MARA 2026-10-09 $11.50 CALL (MARA261009C00011500)\nquote: unavailable"
        assert contract_lines(None, None, "~ATM C near $11.73") == "contract: ~ATM C near $11.73"

    def test_scanner_alert_carries_contract_and_quote(self, monkeypatch):
        from nn_meta import config
        from nn_meta.live import scanner as sc
        monkeypatch.setattr(config, "POOL", "v31")
        sig = sc.Signal(symbol="MARA", strategy="rsi", direction=0, right="C",
                        bar_ts=pd.Timestamp("2026-09-09 16:30"), dte=30, spot=11.73,
                        param_label="entry=35, exit=70, window=14", score=0.58)
        q = {"bid": 1.26, "ask": 1.31, "bid_size": 99, "ask_size": 31,
             "ts": datetime.now(timezone.utc).isoformat(), "source": "stream"}
        title, msg = sc.format_alert(sig, "MARA261009C00011500", q)
        assert title == "[v31] MARA BUY CALL"
        assert "contract: MARA 2026-10-09 $11.50 CALL (MARA261009C00011500)\nquote: bid 1.26 / ask 1.31" in msg
        assert "~ATM" not in msg and "bar: 2026-09-09 16:30:00 UTC · spot $11.73" in msg
        legacy = sc.format_alert(sig)[1]
        assert "contract: ~ATM C near $11.73 strike, ~30 DTE" in legacy and "quote:" not in legacy

    def test_v4_alert_carries_contract_and_quote(self):
        from nn_meta.live.v4_scan import format_v4_alert
        bundle = SimpleNamespace(family="nn", mode="filter", dd_brake=None)
        row = pd.DataFrame([{"symbol": "APH", "strategy": "tv_rating", "dte": 45,
                             "entry_ts": pd.Timestamp("2026-09-09 15:00"), "score": 0.64}]).iloc[0]
        fresh = {"direction": 1, "param_label": "entry_rating=0.50", "spot": 81.44}
        q = {"bid": 4.60, "ask": 5.30, "bid_size": 484, "ask_size": 20, "ts": datetime.now(timezone.utc).isoformat(), "source": "rest"}
        _, msg = format_v4_alert(row, fresh, bundle, False, "APH261016P00082500", q)
        assert "contract: APH 2026-10-16 $82.50 PUT (APH261016P00082500)\nquote: bid 4.60 / ask 5.30 · mid 4.95 · spread 14.1%" in msg
        assert msg.count("\n") == 6 and "bar: 2026-09-09 15:00:00 UTC · spot $81.44" in msg
        assert "\nexit:" in msg
        _, legacy = format_v4_alert(row, fresh, bundle, False)
        assert "contract: ~ATM P near $81.44, ~45 DTE" in legacy

    def test_ledger_records_contract_and_entry_mid(self, tmp_path):
        from nn_meta.live.state import PaperLedger
        led = PaperLedger(tmp_path / "l.json")
        led.open("t1", "APH", "2026-09-09 15:00", 81.44, contract="APH261016P00082500", entry_mid=4.95)
        led.open("t2", "KO", "2026-09-09 15:00", 87.0, contract=None, entry_mid=None)   # unresolved: keys absent
        t = {x["trade_id"]: x for x in PaperLedger(tmp_path / "l.json").open_positions()}
        assert t["t1"]["contract"] == "APH261016P00082500" and t["t1"]["entry_mid"] == 4.95
        assert "contract" not in t["t2"] and t["t2"]["entry_price"] == 87.0
