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


def _digest():
    """Build + persist, mirroring the pre-P1-1 implicit behavior these
    tests were written against (main() now persists only on send success;
    that path has its own dedicated test)."""
    msg, state = heartbeat.build_message()
    heartbeat.persist_state(state)
    return msg

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
        msg = _digest()
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
        msg = _digest()
        assert "v3: 1 pass (1 RTH) · 1 alert · 0 new crashes" in msg

    def test_new_crash_delta_flagged_per_log(self, logs, monkeypatch):
        _seed_state(logs.st, v31={"tracebacks": 21})
        for log in (logs.v3, logs.v4):
            log.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n" + "Traceback\n" * 23)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        msg = _digest()
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
        msg = _digest()
        assert "v3: 2 NEW crash(es)" in msg         # old baseline still honored
        assert msg.count("NEW crash") == 1          # v4's 5 = baseline, not new
        state = json.loads(logs.st.read_text())     # rewritten as new schema
        assert state["logs"]["v4"]["tracebacks"] == 5
        assert state["logs"]["v3"]["passes"] == 1

    def test_corrupt_state_tolerated(self, logs, monkeypatch):
        logs.st.write_text("not json{")
        logs.v3.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "Scanner" in _digest()   # no exception

    def test_first_run_no_false_crash_or_down_warning(self, logs, monkeypatch):
        # no state at all: baselines = current, even during RTH
        logs.v3.write_text("Traceback\n" * 21)
        logs.v4.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = _digest()
        assert "healthy" in msg and "baseline set" in msg


class TestMissingAndStaleLogs:
    def test_missing_logs_are_no_data_not_a_crash(self, logs, monkeypatch):
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        msg = _digest()             # nothing exists at all
        assert "healthy" in msg and "v4: no log yet" in msg

    def test_missing_log_warns_during_rth(self, logs, monkeypatch):
        _seed_state(logs.st)
        logs.v3.write_text("No fresh signals this pass.\n")
        logs.v31.write_text("No fresh signals this pass.\n")   # v4 missing
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = _digest()
        assert "⚠️ v4" in msg and "DOWN" in msg

    def test_zero_scan_passes_during_rth_warns(self, logs, monkeypatch):
        # logs alive but no completed RTH scan since the baseline
        _seed_state(logs.st, v3={"passes": 2}, v4={"passes": 2},
                    v31={"passes": 2})
        for log in (logs.v3, logs.v4, logs.v31):
            log.write_text("Outside RTH — nothing to scan.\n" * 2)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = _digest()
        assert "⚠️ v31: 0 scan passes" in msg and "DOWN" in msg

    def test_stale_log_warns_during_rth(self, logs, monkeypatch):
        _seed_state(logs.st)
        for log in (logs.v3, logs.v4, logs.v31):
            log.write_text("No fresh signals this pass.\n")
        old = time.time() - 3 * 3600
        os.utime(logs.v3, (old, old))               # v3 silent for 3 h
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = _digest()
        assert "⚠️ v3" in msg and "stale" in msg and "DOWN" in msg
        assert "⚠️ v4" not in msg

    def test_no_warn_when_market_closed(self, logs, monkeypatch):
        _seed_state(logs.st)                        # everything at zero, no logs
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "healthy" in _digest()


class TestBacktesterLogErrors:
    def test_fa_collector_errors_excluded(self, logs, monkeypatch):
        logs.bl.write_text(_today(
            "ERROR - [fa.collect] edgar failed: 503",   # collector, not scanner
            "ERROR - [fa.collect] edgar failed: 503",
            "ERROR - [live] AAPL: scan error: boom"))
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "1 error today" in _digest()


class TestMain:
    def test_main_sends_digest_via_notifier(self, logs, monkeypatch):
        n = _Notifier()
        monkeypatch.setattr(heartbeat, "get_notifier", lambda: n)
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        heartbeat.main()
        assert len(n.sent) == 1
        title, msg = n.sent[0]
        assert title == "Scanner heartbeat" and "v3" in msg


# ── 2026-08-16 pre-merge review P1 fixes ─────────────────────────────────────

def test_failed_send_retains_baselines_so_deltas_rereport(logs, monkeypatch):
    """P1-1: a failed notifier POST must not consume the new-crash deltas."""
    logs.v3.write_text("Outside RTH — nothing to scan.\nTraceback (x)\n")
    _digest()                                           # baseline established
    logs.v3.write_text(logs.v3.read_text() + "Traceback (y)\nTraceback (z)\n")

    class _FailNotifier:
        def send(self, msg, title=""):
            return False

    monkeypatch.setattr(heartbeat, "get_notifier", lambda: _FailNotifier())
    heartbeat.main()                                    # send fails
    # deltas were NOT consumed: a later successful digest still reports them
    msg = _digest()
    assert "2 NEW crash(es)" in msg


def test_one_unreadable_log_degrades_to_warning_not_blank_digest(logs):
    """P1-2: an OSError on one expert's log keeps the other experts' lines."""
    logs.v3.write_text("Outside RTH — nothing to scan.\n")
    logs.v4.mkdir()                    # a DIRECTORY: read_text -> IsADirectoryError
    msg = _digest()
    assert "v4: unreadable" in msg and "⚠️ v4: could not read" in msg
    assert "v3:" in msg and "v31:" in msg               # others survive


def test_rotated_log_resets_counters_instead_of_masking(logs):
    """P1-3: counters below baseline mean rotation — count the fresh log,
    don't clamp to zero (which hid real crashes and cried false DOWN)."""
    logs.v3.write_text(("Outside RTH — nothing to scan.\n" * 40)
                     + "Traceback (a)\n" * 3)
    _digest()                                           # baseline: 40 passes, 3 tb
    logs.v3.write_text("Outside RTH — nothing to scan.\n"
                     "Traceback (b)\nTraceback (c)\n")  # rotated + 2 real crashes
    msg = _digest()
    assert "log rotated — counters reset" in msg
    assert "2 NEW crash(es)" in msg                     # not clamped to 0


def test_copytruncate_regrows_to_equal_counts_is_not_false_down(logs, monkeypatch):
    monkeypatch.setattr(heartbeat, 'is_rth', lambda: True)
    for path in (logs.v3,logs.v4,logs.v31):
        path.write_text('No fresh signals this pass.\n'*14)
        path.with_name(path.name+'-20260909').write_text('old archive')
    _digest()
    # Inode and counts stay equal, but this is a NEW day's log generation.
    for path in (logs.v3,logs.v4,logs.v31):
        path.with_name(path.name+'-20260910').write_text(path.read_text())
        path.write_text('No fresh signals this pass.\n'*14)
    msg=_digest()
    assert 'may be DOWN' not in msg
    assert msg.count('14 passes (14 RTH)')==3
    assert msg.count('log rotated — counters reset')==3
    # No more scans really should warn on the next check: don't disable alerts.
    assert '0 scan passes' in _digest()


def test_rotation_regrown_above_baseline_counts_all_new_passes(logs, monkeypatch):
    monkeypatch.setattr(heartbeat, 'is_rth', lambda: False)
    logs.v3.write_text('No fresh signals this pass.\n'*2)
    _digest()
    logs.v3.with_name(logs.v3.name+'-20260910').write_text(logs.v3.read_text())
    logs.v3.write_text('No fresh signals this pass.\n'*3)
    assert 'v3: 3 passes (3 RTH)' in _digest()


def test_compression_does_not_change_rotation_generation(logs, monkeypatch):
    monkeypatch.setattr(heartbeat, 'is_rth', lambda: False)
    logs.v3.write_text('No fresh signals this pass.\n')
    archive=logs.v3.with_name(logs.v3.name+'-20260910')
    archive.write_text('archive');_digest()
    archive.rename(archive.with_name(archive.name+'.gz'))
    with logs.v3.open('a') as stream:stream.write('No fresh signals this pass.\n')
    msg=_digest()
    assert 'v3: 1 pass (1 RTH)' in msg
    assert 'log rotated' not in msg


def test_old_state_migrates_using_rotation_timestamp(logs, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr(heartbeat, 'is_rth', lambda: True)
    _seed_state(logs.st, v3={'passes':14,'rth_scans':14})
    state=json.loads(logs.st.read_text())
    state['at']=datetime.fromtimestamp(time.time()-3600,timezone.utc).isoformat()
    logs.st.write_text(json.dumps(state))
    for path in (logs.v3,logs.v4,logs.v31):path.write_text('No fresh signals this pass.\n'*14)
    logs.v3.with_name(logs.v3.name+'-20260910').write_text('rotated after last successful heartbeat')
    msg=_digest()
    assert 'v3: 14 passes (14 RTH)' in msg
    assert '⚠️ v3: 0 scan passes' not in msg
    assert 'log_generation' in json.loads(logs.st.read_text())['logs']['v3']


def test_old_archive_does_not_mask_genuine_zero_scans(logs, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr(heartbeat, 'is_rth', lambda: True)
    _seed_state(logs.st,v3={'passes':1,'rth_scans':1})
    state=json.loads(logs.st.read_text());state['at']=datetime.now(timezone.utc).isoformat()
    logs.st.write_text(json.dumps(state))
    logs.v3.write_text('No fresh signals this pass.\n')
    archive=logs.v3.with_name(logs.v3.name+'-20260909');archive.write_text('old')
    os.utime(archive,(time.time()-7200,time.time()-7200))
    assert '⚠️ v3: 0 scan passes' in _digest()
