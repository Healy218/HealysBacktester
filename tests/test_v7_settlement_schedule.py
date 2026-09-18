from copy import deepcopy

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.settlement_schedule import ReportedSettlementSchedule, normalize_reported_settlements


def fixture():
    pairs = [('2025-01-07', '2025-01-08'), ('2025-01-08', '2025-01-09'),
             ('2025-01-10', '2025-01-13'), ('2025-01-13', '2025-01-14')]
    raw = [dict(date=d, open='09:30', close='16:00', settlement_date=s) for d, s in pairs]
    calendar = dict(coverage_start='2025-01-07', coverage_end='2025-01-13', sessions=raw)
    doc = normalize_reported_settlements(raw, calendar, start=calendar['coverage_start'],
        end=calendar['coverage_end'], source_identity='capture')
    return raw, calendar, doc


def clock(day):
    return int(pd.Timestamp(day+'T15:00Z').value)


def test_settlement_on_exchange_closed_day_is_preserved_and_cash_waits_for_open():
    _, c, d = fixture(); trading = SessionCalendar(c)
    assert trading.bounds('2025-01-09') is None
    schedule = ReportedSettlementSchedule(d, trading)
    assert schedule.settlement(clock('2025-01-08')) == (
        '2025-01-09', int(pd.Timestamp('2025-01-10T14:30Z').value))
    with pytest.raises(ValueError): schedule.settlement(clock('2025-01-09'))
    with pytest.raises(ValueError): schedule.settlement(clock('2025-01-13'))


def test_t_plus_one_transition_retains_equal_reported_settlements():
    raw = [dict(date=d, settlement_date=s, open='09:30', close='16:00') for d, s in
        [('2024-05-24', '2024-05-29'), ('2024-05-28', '2024-05-29'),
         ('2024-05-29', '2024-05-30'), ('2024-05-30', '2024-05-31')]]
    c = dict(coverage_start='2024-05-24', coverage_end='2024-05-30', sessions=raw)
    d = normalize_reported_settlements(raw, c, start=c['coverage_start'], end=c['coverage_end'], source_identity='capture')
    schedule = ReportedSettlementSchedule(d, SessionCalendar(c))
    assert schedule.settlement(clock('2024-05-24')) == schedule.settlement(clock('2024-05-28'))


@pytest.mark.parametrize('change', ['missing_field', 'changed_normalization', 'duplicate_raw',
    'missing_date', 'duplicate_date', 'early_settlement', 'outside_coverage', 'unordered', 'posting_claim'])
def test_rejects_guessed_incomplete_or_altered_calendar(change):
    raw, c, d = deepcopy(fixture())
    if change == 'missing_field': raw[0].pop('settlement_date'); c['sessions'] = raw
    if change == 'changed_normalization': raw = deepcopy(raw); raw[0]['settlement_date'] = '2025-01-10'
    if change == 'duplicate_raw': raw.append(deepcopy(raw[0]))
    if change in ('missing_field', 'changed_normalization', 'duplicate_raw'):
        with pytest.raises(ValueError):
            normalize_reported_settlements(raw, c, start=c['coverage_start'], end=c['coverage_end'], source_identity='capture')
        return
    if change == 'missing_date': d['trade_settlements'].pop(0)
    if change == 'duplicate_date': d['trade_settlements'].insert(1, deepcopy(d['trade_settlements'][0]))
    if change == 'early_settlement': d['trade_settlements'][0]['settlement_date'] = '2025-01-07'
    if change == 'outside_coverage': d['coverage_end'] = '2025-01-14'
    if change == 'unordered': d['trade_settlements'].reverse()
    if change == 'posting_claim': d['broker_posting_verified'] = True
    with pytest.raises(ValueError): ReportedSettlementSchedule(d, SessionCalendar(c))
