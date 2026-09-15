"""Receipt-backed V7 stock/session coverage; absence is never an IPO verdict."""
from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.download_v7_data import completed, digest


def receipt_frame(root, receipt_path):
    receipt_path = Path(receipt_path)
    doc = json.loads(receipt_path.read_text())
    expected_path = Path(root) / doc['task']['key'] / 'complete.json'
    if expected_path.resolve() != receipt_path.resolve() or completed(Path(root), doc['task']) != doc:
        raise ValueError('Stock receipt does not match the verified task path')
    paths = [receipt_path.parent / name for name in doc['files'] if name.endswith('.parquet')]
    if len(paths) != 1:
        raise ValueError('Expected exactly one stock parquet in verified receipt')
    frame = pd.read_parquet(paths[0])
    if len(frame) != doc['rows']:
        raise ValueError('Stock receipt row count mismatch')
    stamps = frame.timestamp
    if not isinstance(stamps.dtype, pd.DatetimeTZDtype) or stamps.isna().any():
        raise ValueError('Stock times must be nonmissing and timezone-aware')
    if not stamps.is_monotonic_increasing or stamps.duplicated().any():
        raise ValueError('Stock timestamps are unordered/duplicated')
    if (stamps.astype('int64') % 60_000_000_000 != 0).any():
        raise ValueError('Stock timestamps must be exact minute opens')
    values = frame[['Open', 'High', 'Low', 'Close', 'Volume']]
    if (not np.isfinite(values.to_numpy()).all() or (values.iloc[:, :4] <= 0).any().any()
            or (values.Volume < 0).any()
            or (values.High < values[['Open', 'Low', 'Close']].max(axis=1)).any()
            or (values.Low > values[['Open', 'High', 'Close']].min(axis=1)).any()):
        raise ValueError('Invalid stock OHLCV')
    return doc, frame


def audit_pair(root, symbol, year, calendar):
    paths = {basis: Path(root) / 'stock_1m' / basis / symbol / str(year) / 'complete.json'
             for basis in ('raw', 'all')}
    if not all(p.exists() for p in paths.values()):
        raise ValueError('Missing raw/adjusted completion receipt')
    raw_doc, raw = receipt_frame(root, paths['raw'])
    adj_doc, adjusted = receipt_frame(root, paths['all'])
    if raw_doc['task'] != {**adj_doc['task'], 'adjustment': 'raw',
                           'key': f'stock_1m/raw/{symbol}/{year}'}:
        raise ValueError('Price-basis request identities differ')
    same_times = raw.timestamp.equals(adjusted.timestamp)
    stamps = pd.DatetimeIndex(raw.timestamp)
    counts, daily = [], []
    for session in calendar['sessions']:
        day = session['date']
        opening = pd.Timestamp(day + ' ' + session['open'], tz='America/New_York').tz_convert('UTC')
        closing = pd.Timestamp(day + ' ' + session['close'], tz='America/New_York').tz_convert('UTC')
        if not pd.Timestamp(raw_doc['task']['start']) <= opening < pd.Timestamp(raw_doc['task']['end']):
            continue
        expected = int((closing - opening).total_seconds() // 60)
        lo, hi = stamps.searchsorted(opening), stamps.searchsorted(closing)
        present = int(hi - lo)
        counts.append({'symbol': symbol, 'date': day, 'expected_minutes': expected,
                       'observed_minutes': present, 'unobserved_minutes': expected - present})
        for basis, frame in (('raw', raw), ('all', adjusted)):
            selected = frame.iloc[lo:hi] if same_times else frame[(frame.timestamp >= opening) & (frame.timestamp < closing)]
            if len(selected):
                daily.append({'symbol': symbol, 'date': day, 'basis': basis,
                              'Open': selected.Open.iloc[0], 'High': selected.High.max(),
                              'Low': selected.Low.min(), 'Close': selected.Close.iloc[-1],
                              'Volume': selected.Volume.sum()})
    summary = {'symbol': symbol, 'year': str(year), 'raw_rows': len(raw),
               'adjusted_rows': len(adjusted), 'timestamp_parity': same_times,
               'empty': raw.empty and adjusted.empty,
               'first_observed': None if raw.empty else stamps[0].isoformat(),
               'last_observed': None if raw.empty else stamps[-1].isoformat(),
               'sessions': len(counts), 'zero_observation_sessions': sum(r['observed_minutes'] == 0 for r in counts),
               'unobserved_regular_minutes': sum(r['unobserved_minutes'] for r in counts),
               'receipt_sha256': {b: digest(p) for b, p in paths.items()},
               'calendar_sha256': __import__('hashlib').sha256(json.dumps(calendar, sort_keys=True).encode()).hexdigest(),
               'eligibility_validated': False,
               'missingness_policy': 'unobserved minutes require listing/alias and no-trade evidence; never fill'}
    if same_times and len(raw):
        ratios = adjusted[['Open', 'High', 'Low', 'Close']].to_numpy() / raw[['Open', 'High', 'Low', 'Close']].to_numpy()
        summary['ohlc_adjustment_ratio_spread_max'] = float(np.max(np.ptp(ratios, axis=1)))
    return summary, pd.DataFrame(counts), pd.DataFrame(daily)
