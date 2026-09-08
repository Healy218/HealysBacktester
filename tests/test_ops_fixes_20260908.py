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

    def test_weekday_fallback_without_calendar_treats_monday_as_session(self):
        # No captured calendar: the Mon-Fri rule applies (production always has one).
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
