from types import SimpleNamespace
import pandas as pd
import pytest

from scripts.check_v6_research_window import allowed


@pytest.mark.parametrize('clock,expected', [
    ('2026-09-28T12:59:59Z', True), ('2026-09-28T13:00:00Z', False),
    ('2026-09-28T13:31:00Z', False), ('2026-09-28T20:14:59Z', False),
    ('2026-09-28T20:15:00Z', True),
])
def test_delayed_morning_timer_cannot_start_after_market_open(clock, expected):
    calendar = SimpleNamespace(bounds=lambda day: (pd.Timestamp('2026-09-28 13:30'),
                                                   pd.Timestamp('2026-09-28 20:00')))
    assert allowed(calendar, clock) is expected


def test_short_session_releases_research_after_actual_close():
    calendar = SimpleNamespace(bounds=lambda day: (pd.Timestamp('2026-11-27 14:30'),
                                                   pd.Timestamp('2026-11-27 18:00')))
    assert not allowed(calendar, '2026-11-27T18:14:59Z')
    assert allowed(calendar, '2026-11-27T18:15:00Z')
