"""Integration of streamed-session completeness with the current REST loader."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from nn_meta.live import run_live
from nn_meta.live.feeds.barstore import BarStore


@pytest.mark.parametrize('fault', ['missing_bucket', 'incomplete_bucket', 'read_error'])
def test_stream_gap_or_read_failure_uses_complete_rest_session(monkeypatch, fault):
    now = datetime(2026, 9, 4, 14, 16, tzinfo=timezone.utc)
    index = pd.date_range('2026-09-04 13:30', periods=3, freq='15min', name='timestamp')
    rest = pd.DataFrame({c: [100., 101., 102.] for c in run_live._OHLCV}, index=index)
    calls = []
    def load(symbol, start, end, interval, **kwargs):
        calls.append(kwargs)
        return rest if kwargs.get('force_download') else rest.iloc[:0]
    def stream(self, symbol, now=None, days=None):
        if fault == 'incomplete_bucket':
            raise ValueError('incomplete streamed 15m bar')
        if fault == 'read_error':
            raise OSError('unreadable parquet')
        return rest.iloc[[0, 2]]
    monkeypatch.setattr(run_live, '_feed_is_fresh', lambda _: True)
    monkeypatch.setattr(run_live.vbt_data_loader, 'load_price_data_smart', load)
    monkeypatch.setattr(BarStore, 'read_15m', stream)
    pd.testing.assert_frame_equal(run_live._bar_loader('SPY', now=now), rest, check_freq=False)
    assert calls == [{}, {'force_download': True, 'use_cache': False}]
