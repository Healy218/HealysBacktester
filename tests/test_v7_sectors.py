import pandas as pd
import pytest
from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.sectors import DatedSectors, assign_sessions, classify


def test_sector_classification_is_business_and_security_type_based():
    assert classify(dict(type='CS', sic_code='3674'))[0] == 'semis'
    assert classify(dict(type='CS', sic_code='3571'))[0] == 'tech'
    assert classify(dict(type='CS', sic_code='6199', description='Operates a cryptocurrency exchange.'))[0] == 'crypto'
    assert classify(dict(type='CS', sic_code='6199', description='Banking and lending.'))[0] == 'fin'
    assert classify(dict(type='CS', sic_code='6770'))[0] == 'spec'
    assert classify(dict(type='CS', sic_code='2834'))[0] == 'defensive'
    assert classify(dict(type='CS', sic_code='1311'))[0] == 'cyclical'
    assert classify(dict(type='CS', ticker='AAPL')) == (None, 'sic_missing_or_invalid')
    assert classify(dict(type='ETF', name='State Street SPDR S&P 500 ETF Trust'))[0] == 'idx_etf'
    assert classify(dict(type='ETF', name='ProShares UltraPro Short S&P 500'))[0] == 'sec_etf'
    assert classify(dict(type='ETF', name='Financial Select Sector SPDR Fund', sic_code='6022'))[0] == 'sec_etf'


def test_sector_asof_preserves_unknown_and_does_not_follow_reused_ticker():
    days = ['2024-05-06', '2024-05-07', '2024-05-08']
    calendar = SessionCalendar(dict(coverage_start=days[0], coverage_end=days[-1],
        sessions=[dict(date=d, open='09:30', close='16:00') for d in days]))
    sessions = pd.DataFrame([dict(date=d, security_id=i, membership_ticker='SAME') for d in days for i in ['old', 'new']])
    obs = pd.DataFrame([dict(security_id=i, reference_date=d, sector=s, reason='fixture',
        source_receipt='receipt', source_sha256='digest') for i,d,s in
        [('old', '2024-05-03', 'tech'), ('old', '2024-05-07', 'crypto'), ('new', '2024-05-07', 'fin')]])
    mapping = assign_sessions(sessions, obs, calendar)
    old = DatedSectors(mapping[mapping.security_id.eq('old')], security_id='old')
    new = DatedSectors(mapping[mapping.security_id.eq('new')], security_id='new')
    assert old.at('2024-05-07T20:00Z')['sector'] == 'tech'
    assert old.at('2024-05-08T13:30Z')['sector'] == 'crypto'
    assert new.at('2024-05-07T20:00Z')['sector'] is None
    assert new.at('2024-05-08T13:30Z')['sector'] == 'fin'
    with pytest.raises(ValueError, match='No sector record'):
        old.at('2024-05-08T13:29:59Z')
    with pytest.raises(ValueError, match='No sector record'):
        old.at('2024-05-09T14:00Z')
    with pytest.raises(ValueError, match='security-bound'):
        DatedSectors(mapping, security_id='old')
    broken = mapping[mapping.security_id.eq('old')].copy()
    broken['reference_date'] = broken.date
    with pytest.raises(ValueError, match='future reference'):
        DatedSectors(broken, security_id='old')
