import pytest
from nn_meta.etfe.purchase_policy_v2 import check_purchase,dte_fraction,expiry_entry_gate,iv_time_years


@pytest.mark.parametrize('expiry,allowed',[('2026-10-01',False),('2026-10-02',True),
    ('2026-10-07',True),('2026-10-08',False)])
def test_actual_zero_to_five_calendar_dte(expiry,allowed):
    assert check_purchase(expiry,'2026-10-02T15:00:00Z',target=0)['dte_eligible'] is allowed


def test_zero_dte_needs_signal_clock_and_strict_expiry_cutoff():
    args=dict(expiration_date='2026-10-02',attempt_at='2026-10-02T19:44:59Z',target=0,
        signal_qualifies=True,expiry_close='2026-10-02T20:00:00Z')
    assert expiry_entry_gate(**args)['entry_eligible']
    assert not expiry_entry_gate(**dict(args,signal_qualifies=False))['entry_eligible']
    assert not expiry_entry_gate(**dict(args,expiry_close=None))['entry_eligible']
    assert not expiry_entry_gate(**dict(args,attempt_at='2026-10-02T19:45:00Z'))['entry_eligible']
    assert not expiry_entry_gate(**dict(args,attempt_at='2026-10-02T20:01:00Z'))['entry_eligible']


def test_new_york_day_iv_clock_and_feature_zero():
    assert check_purchase('2026-10-02','2026-10-03T00:00:00Z',target=0)['actual_calendar_dte']==0
    assert dte_fraction('2026-10-02','2026-10-02T15:00:00Z')==0
    assert iv_time_years('2026-10-02T19:00:00Z','2026-10-02T20:00:00Z')==3600/(365*86400)
    assert iv_time_years('2026-10-02T20:00:00Z','2026-10-02T20:00:00Z') is None
    assert iv_time_years('2026-10-02T19:00:00Z',None) is None
    assert not check_purchase('2026-10-07','2026-10-02T15:00:00Z',target=7,weekly_eligible=True)['dte_eligible']


def test_inconsistent_or_naive_expiry_clocks_rejected():
    with pytest.raises(ValueError):
        expiry_entry_gate('2026-10-02','2026-10-02T15:00:00Z',target=0,signal_qualifies=True,expiry_close='2026-10-03T20:00:00Z')
    with pytest.raises(ValueError):
        iv_time_years('2026-10-02T15:00:00','2026-10-02T20:00:00Z')
