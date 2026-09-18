from unittest.mock import patch
import pandas as pd
from nn_meta.session_calendar import SessionCalendar
from scripts.v6_forward_ops import health


def calendar():
    return SessionCalendar({'coverage_start':'2026-09-11','coverage_end':'2026-09-15',
        'sessions':[{'date':'2026-09-14','open':'09:30','close':'16:00'}]})


def test_watcher_waits_for_first_result_and_detects_missed_deadline():
    assert health({},calendar(),pd.Timestamp('2026-09-14T13:50:59Z'))['status']=='idle'
    assert health({},calendar(),pd.Timestamp('2026-09-14T13:51:00Z'))['status']=='failed'
    status={'signal_clock':'2026-09-14T13:45:20Z','status':'recorded','phase':'complete'}
    assert health(status,calendar(),pd.Timestamp('2026-09-14T13:52:00Z'))['status']=='healthy'
    status['replay']=True
    assert health(status,calendar(),pd.Timestamp('2026-09-14T13:52:00Z'))['status']=='failed'


def test_watcher_checks_final_bar_after_close_and_a_new_pass_in_progress():
    status={'signal_clock':'2026-09-14T20:00:20Z','status':'running','phase':'detect'}
    assert health(status,calendar(),pd.Timestamp('2026-09-14T20:03Z'))['status']=='healthy'
    assert health(status,calendar(),pd.Timestamp('2026-09-14T20:06Z'))['status']=='failed'
    status.update(status='recorded',phase='complete')
    assert health(status,calendar(),pd.Timestamp('2026-09-14T20:06Z'))['status']=='healthy'


def test_watcher_reports_explicit_live_failures_and_ignores_weekends():
    assert health({},calendar(),pd.Timestamp('2026-09-13T18:00Z'))['status']=='idle'
    status={'signal_clock':'2026-09-14T13:45:20Z','status':'failed','error':'no fresh quote'}
    assert health(status,calendar(),pd.Timestamp('2026-09-14T13:52Z'))['reason']=='no fresh quote'
