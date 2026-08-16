# tests/test_heartbeat.py
"""Heartbeat: per-expert pass/alert/crash deltas across the three cron logs,
old-schema state migration, missing-log tolerance, and the warn/healthy
branch selection."""
import json
import os
import time
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.live import heartbeat

_ZEROS = {"passes": 0, "rth_scans": 0, "alerts": 0, "tracebacks": 0}


@pytest.fixture
def logs(tmp_path, monkeypatch):
    ns = SimpleNamespace(
        bl=tmp_path / "backtester.log",
        v3=tmp_path / "live_cron.log",
        v4=tmp_path / "v4_cron.log",
        v31=tmp_path / "v31_cron.log",
        st=tmp_path / ".hb_state.json")
    monkeypatch.setattr(heartbeat, "BACKTESTER_LOG", ns.bl)
    monkeypatch.setattr(heartbeat, "STATE", ns.st)
    monkeypatch.setattr(heartbeat, "EXPERT_LOGS",
                        {"v3": ns.v3, "v4": ns.v4, "v31": ns.v31})
    return ns


def _today(*msgs):
    d = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    return "\n".join(f"{d} 15:0{i},000 - backtester - {m}"
                     for i, m in enumerate(msgs))


def _seed_state(st, **overrides):
    """New-schema baselines (all zero unless overridden) — makes every
    expert 'not first run' so deltas equal the logs' totals."""
    st.write_text(json.dumps({"logs": {
        k: {**_ZEROS, **overrides.get(k, {})} for k in ("v3", "v4", "v31")}}))


class _Notifier:
    def __init__(self):
        self.sent = []

    def send(self, message, title="Signal"):
        self.sent.append((title, message))
        return True


class TestPerExpertCounts:
    def test_healthy_digest_line_per_expert(self, logs, monkeypatch):
        _seed_state(logs.st)
        logs.bl.write_text(_today("INFO - nothing relevant"))
        logs.v3.write_text("Outside RTH — nothing to scan.\n"
                          "No fresh signals this pass.\n"
                          "No fresh signals this pass.\n"
                          "2 signal(s) alerted: NVDA, AMD\n")
        logs.v4.write_text("Outside RTH — nothing to scan.\n"
                          "[v4] scanned 118 · alerted 1 · delivered 1 · errors 0\n")
        logs.v31.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = heartbeat.build_message()
        assert "healthy" in msg
        assert "v3: 4 passes (3 RTH) · 2 alerts · 0 new crashes" in msg
        assert "v4: 2 passes (1 RTH) · 1 alert · 0 new crashes" in msg
        assert "v31: 1 pass (1 RTH) · 0 alerts · 0 new crashes" in msg

    def test_deltas_are_since_last_heartbeat(self, logs, monkeypatch):
        _seed_state(logs.st, v3={"passes": 3, "rth_scans": 2, "alerts": 1})
        logs.v3.write_text("No fresh signals this pass.\n" * 2
                           + "2 signal(s) alerted: NVDA, AMD\n"
                           + "Outside RTH — nothing to scan.\n")  # totals: 4/3/2
        logs.v4.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        msg = heartbeat.build_message()
        assert "v3: 1 pass (1 RTH) · 1 alert · 0 new crashes" in msg

    def test_new_crash_delta_flagged_per_log(self, logs, monkeypatch):
        _seed_state(logs.st, v31={"tracebacks": 21})
        for log in (logs.v3, logs.v4):
            log.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n" + "Traceback\n" * 23)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        msg = heartbeat.build_message()
        assert "v31: 2 NEW crash(es)" in msg
        assert msg.count("NEW crash") == 1          # only the crashing expert


class TestStateSchema:
    def test_old_single_log_schema_migrates_without_explosion(self, logs,
                                                              monkeypatch):
        logs.st.write_text('{"tracebacks": 21, "at": "2026-08-14"}')  # old schema
        logs.v3.write_text("No fresh signals this pass.\n" + "Traceback\n" * 23)
        logs.v4.write_text("[v4] scanned 9 · alerted 0 · delivered 0 · errors 0\n"
                           + "Traceback\n" * 5)     # pre-existing, NOT new
        logs.v31.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        msg = heartbeat.build_message()
        assert "v3: 2 NEW crash(es)" in msg         # old baseline still honored
        assert msg.count("NEW crash") == 1          # v4's 5 = baseline, not new
        state = json.loads(logs.st.read_text())     # rewritten as new schema
        assert state["logs"]["v4"]["tracebacks"] == 5
        assert state["logs"]["v3"]["passes"] == 1

    def test_corrupt_state_tolerated(self, logs, monkeypatch):
        logs.st.write_text("not json{")
        logs.v3.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "Scanner" in heartbeat.build_message()   # no exception

    def test_first_run_no_false_crash_or_down_warning(self, logs, monkeypatch):
        # no state at all: baselines = current, even during RTH
        logs.v3.write_text("Traceback\n" * 21)
        logs.v4.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = heartbeat.build_message()
        assert "healthy" in msg and "baseline set" in msg


class TestMissingAndStaleLogs:
    def test_missing_logs_are_no_data_not_a_crash(self, logs, monkeypatch):
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        msg = heartbeat.build_message()             # nothing exists at all
        assert "healthy" in msg and "v4: no log yet" in msg

    def test_missing_log_warns_during_rth(self, logs, monkeypatch):
        _seed_state(logs.st)
        logs.v3.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n")   # v4 missing
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = heartbeat.build_message()
        assert "⚠️ v4" in msg and "DOWN" in msg

    def test_zero_scan_passes_during_rth_warns(self, logs, monkeypatch):
        # logs alive but no completed RTH scan since the baseline
        _seed_state(logs.st, v3={"passes": 2}, v4={"passes": 2},
                    v31={"passes": 2})
        for log in (logs.v3, logs.v4, logs.v31):
            log.write_text("Outside RTH — nothing to scan.\n" * 2)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = heartbeat.build_message()
        assert "⚠️ v31: 0 scan passes" in msg and "DOWN" in msg

    def test_stale_log_warns_during_rth(self, logs, monkeypatch):
        _seed_state(logs.st)
        for log in (logs.v3, logs.v4, logs.v31):
            log.write_text("No fresh signals this pass.\n")
        old = time.time() - 3 * 3600
        os.utime(logs.v3, (old, old))               # v3 silent for 3 h
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = heartbeat.build_message()
        assert "⚠️ v3" in msg and "stale" in msg and "DOWN" in msg
        assert "⚠️ v4" not in msg

    def test_no_warn_when_market_closed(self, logs, monkeypatch):
        _seed_state(logs.st)                        # everything at zero, no logs
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "healthy" in heartbeat.build_message()


class TestBacktesterLogErrors:
    def test_fa_collector_errors_excluded(self, logs, monkeypatch):
        logs.bl.write_text(_today(
            "ERROR - [fa.collect] edgar failed: 503",   # collector, not scanner
            "ERROR - [fa.collect] edgar failed: 503",
            "ERROR - [live] AAPL: scan error: boom"))
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "1 error today" in heartbeat.build_message()


class TestMain:
    def test_main_sends_digest_via_notifier(self, logs, monkeypatch):
        n = _Notifier()
        monkeypatch.setattr(heartbeat, "get_notifier", lambda: n)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        heartbeat.main()
        assert len(n.sent) == 1
        title, msg = n.sent[0]
        assert title == "Scanner heartbeat" and "v3" in msg
