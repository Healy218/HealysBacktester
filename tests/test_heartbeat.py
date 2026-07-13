# tests/test_heartbeat.py
"""Heartbeat: today-line counting, new-crash delta, and the warn/healthy
branch selection."""
import pandas as pd
import pytest

from nn_meta.live import heartbeat


@pytest.fixture
def logs(tmp_path, monkeypatch):
    bl = tmp_path / "backtester.log"
    cl = tmp_path / "live_cron.log"
    st = tmp_path / ".hb_state.json"
    monkeypatch.setattr(heartbeat, "BACKTESTER_LOG", bl)
    monkeypatch.setattr(heartbeat, "CRON_LOG", cl)
    monkeypatch.setattr(heartbeat, "STATE", st)
    return bl, cl, st


def _today(*msgs):
    d = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    return "\n".join(f"{d} 15:0{i},000 - backtester - {m}"
                     for i, m in enumerate(msgs))


class TestHeartbeat:
    def test_healthy_counts_passes_and_signals(self, logs, monkeypatch):
        bl, cl, _ = logs
        bl.write_text(_today(
            "INFO - [live] NN filter enabled (threshold 0.60)",
            "INFO - [live] NN filter enabled (threshold 0.60)",
            "INFO - [notify:telegram] sent: NVDA BUY CALL"))
        cl.write_text("clean\n")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        msg = heartbeat.build_message()
        assert "healthy" in msg and "2 passes" in msg and "1 signal" in msg

    def test_warns_when_no_passes_during_rth(self, logs, monkeypatch):
        bl, cl, _ = logs
        bl.write_text(_today("INFO - nothing relevant"))
        cl.write_text("")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        assert "0 passes" in heartbeat.build_message() and "DOWN" in \
            heartbeat.build_message()

    def test_no_warn_when_closed(self, logs, monkeypatch):
        bl, cl, _ = logs
        bl.write_text("")
        cl.write_text("")
        monkeypatch.setattr(heartbeat, "is_rth", lambda: False)
        assert "healthy" in heartbeat.build_message()

    def test_new_crash_delta_flagged(self, logs, monkeypatch):
        bl, cl, st = logs
        bl.write_text(_today("INFO - [live] NN filter enabled (threshold 0.60)"))
        st.write_text('{"tracebacks": 21}')          # baseline
        cl.write_text("Traceback\n" * 23)            # 2 new
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        assert "2 NEW crash" in heartbeat.build_message()

    def test_first_run_no_false_crash(self, logs, monkeypatch):
        bl, cl, st = logs
        bl.write_text(_today("INFO - [live] NN filter enabled (threshold 0.60)"))
        cl.write_text("Traceback\n" * 21)            # no state yet
        monkeypatch.setattr(heartbeat, "is_rth", lambda: True)
        assert "healthy" in heartbeat.build_message()   # baseline = current
