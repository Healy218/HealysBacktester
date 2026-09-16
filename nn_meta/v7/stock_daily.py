"""Bounded regular-session daily stock facts from immutable Alpaca minute captures.

These are raw observations, not adjusted features, official closing-auction
prices, or evidence of listing/identity outside the joined membership dates.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.coverage import receipt_frame
from nn_meta.v7.scope import HISTORY_START, HISTORY_END
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

POLICY = 'v7-raw-session-daily-v1'
ROOT = Path(__file__).resolve().parents[2]


def source_hashes():
    names = ['nn_meta/v7/stock_daily.py', 'nn_meta/v7/coverage.py', 'nn_meta/v7/storage.py',
             'nn_meta/v7/scope.py', 'nn_meta/session_calendar.py', 'scripts/download_v7_data.py',
             'scripts/build_v7_stock_daily.py', 'nn_meta/v7/runtime.py']
    return {str(ROOT/name): sha(ROOT/name) for name in names}


def aggregate_daily(raw, calendar, *, symbol, year):
    """Retain each captured calendar session, including explicit empty sessions."""
    if (not symbol or type(year) is not int or not 2022 <= year <= 2026
            or not isinstance(raw.timestamp.dtype, pd.DatetimeTZDtype)
            or raw.timestamp.isna().any() or raw.timestamp.duplicated().any()
            or not raw.timestamp.is_monotonic_increasing):
        raise ValueError('Explicit symbol/year and ordered aware observations required')
    stamps = pd.DatetimeIndex(raw.timestamp)
    if (stamps.asi8 % 60_000_000_000).any():
        raise ValueError('Exact minute observations required')
    sessions = sorted(d for d in calendar.sessions if HISTORY_START <= d <= HISTORY_END and int(d[:4]) == year)
    rows = []
    for day in sessions:
        opening, closing = [v.tz_localize('UTC') for v in calendar.bounds(day)]
        lo, hi = stamps.searchsorted(opening), stamps.searchsorted(closing)
        frame = raw.iloc[lo:hi]
        expected = int((closing-opening).total_seconds()//60)
        if len(frame) > expected:
            raise ValueError('More minute observations than regular-session slots')
        row = dict(stock_ticker=symbol, source_date=day, observed_minutes=len(frame),
            expected_minutes=expected, session_open_ns=opening.value, available_ns=closing.value,
            first_observed_ns=None, last_observed_ns=None, raw_open=np.nan,
            raw_high=np.nan, raw_low=np.nan, raw_close=np.nan, raw_volume=np.nan)
        if len(frame):
            values = frame[['Open', 'High', 'Low', 'Close', 'Volume']]
            if (not np.isfinite(values.to_numpy()).all() or (values.iloc[:, :4] <= 0).any().any()
                    or (values.Volume < 0).any() or (frame.High < frame[['Open','Low','Close']].max(axis=1)).any()
                    or (frame.Low > frame[['Open','High','Close']].min(axis=1)).any()):
                raise ValueError('Invalid observed raw daily inputs')
            row.update(raw_open=float(frame.Open.iloc[0]), raw_high=float(frame.High.max()),
                       raw_low=float(frame.Low.min()), raw_close=float(frame.Close.iloc[-1]),
                       raw_volume=float(frame.Volume.sum()), first_observed_ns=int(stamps[lo].value),
                       last_observed_ns=int(stamps[hi-1].value))
        rows.append(row)
    if not rows:
        raise ValueError('Calendar has no scoped sessions for this year')
    result = pd.DataFrame(rows)
    for field in ('first_observed_ns', 'last_observed_ns'):
        # Build from the original Python ints, never a float64 intermediate.
        result[field] = pd.array([r[field] for r in rows], dtype='Int64')
    return result


def build_shard(source, symbol, year, output, *, reserve_gib=100):
    from scripts.download_v7_data import disk_guard
    source, output = Path(source).resolve(), Path(output).resolve()
    if type(reserve_gib) is not int or reserve_gib < 0:
        raise ValueError('Nonnegative disk reserve required')
    calendar_path = source/'calendar.json'
    source_path = source/f'stock_1m/raw/{symbol}/{year}/complete.json'
    doc, raw = receipt_frame(source, source_path)
    if (doc['task'].get('kind') != 'stock' or doc['task'].get('adjustment') != 'raw'
            or doc['task'].get('symbol') != symbol):
        raise ValueError('Alpaca raw stock task required')
    calendar = SessionCalendar(json.loads(calendar_path.read_text()))
    inputs = {str(p): sha(p) for p in (calendar_path, source_path)}
    # Bind the actual payload hashes too: a receipt file alone cannot detect an
    # in-place data mutation while aggregation is running.
    inputs.update({str(source_path.parent/name): digest for name, digest in doc['files'].items()})
    sources = source_hashes()
    declaration = dict(schema=POLICY, stock_ticker=symbol, year=year,
        start=HISTORY_START, end=HISTORY_END, inputs=inputs, sources=sources,
        close_policy='last observed regular-session minute; not official auction close',
        availability='session close; downstream daily features use next trading open',
        price_basis='raw Alpaca', missing_policy='no fill; explicit zero observations',
        reserve_gib=reserve_gib, research_ready=False)
    if output.exists():
        verify(output, expected_identity=identity(declaration))
        return json.loads((output/'report.json').read_text())
    disk_guard(source, reserve_gib)
    frame = aggregate_daily(raw, calendar, symbol=symbol, year=year)
    report = dict(stock_ticker=symbol, year=year, sessions=len(frame),
        observed_sessions=int(frame.observed_minutes.gt(0).sum()),
        zero_sessions=int(frame.observed_minutes.eq(0).sum()),
        regular_minutes=int(frame.observed_minutes.sum()), research_ready=False)
    with transaction(output) as temp:
        frame.to_parquet(temp/'daily.parquet', index=False)
        if any(sha(p) != digest for p, digest in {**inputs, **sources}.items()):
            raise ValueError('Daily stock source changed during aggregation')
        disk_guard(source, reserve_gib)
        (temp/'declaration.json').write_text(json.dumps(declaration, indent=2)+'\n')
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        receipt(temp, dict(identity=identity(declaration), research_ready=False))
    return report


def join_eligible(eligible, daily):
    """Exact-date coverage mappings are the only security identity assignment."""
    if (eligible.duplicated(['security_id', 'date']).any()
            or daily.duplicated(['stock_ticker', 'source_date']).any()):
        raise ValueError('Duplicate security/day or stock/day')
    result = eligible.merge(daily, left_on=['stock_ticker','date'],
        right_on=['stock_ticker','source_date'], how='left', validate='many_to_one',
        suffixes=('_coverage',''), indicator=True)
    if (not result._merge.eq('both').all()
            or not result.observed_minutes.eq(result.observed_minutes_coverage).all()):
        raise ValueError('Daily observations differ from the active coverage inventory')
    return result.drop(columns=['_merge','observed_minutes_coverage'])
