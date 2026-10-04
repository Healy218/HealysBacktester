import pytest
from nn_meta.etfe.purchase_policy import check_purchase, dte_fraction, purchase_dte, load_scope


@pytest.mark.parametrize('expiry,allowed', [('2026-10-02',False),('2026-10-03',True),
    ('2026-10-07',True),('2026-10-08',False),('2026-10-09',False),('2026-10-11',False)])
def test_entry_or_roll_requires_actual_one_to_five_days(expiry,allowed):
    assert check_purchase(expiry,'2026-10-02T15:00:00Z',target=5)['dte_eligible'] is allowed


def test_new_york_day_and_calendar_days():
    assert purchase_dte('2026-10-07','2026-10-03T00:00:00Z') == 5
    assert purchase_dte('2026-10-05','2026-10-02T15:00:00Z') == 3
    with pytest.raises(ValueError):
        purchase_dte('2026-10-07','2026-10-02T15:00:00')


def test_seven_target_removed_and_weekly_targets_need_eligibility():
    stamp='2026-10-02T15:00:00Z'
    assert not check_purchase('2026-10-07',stamp,target=7,weekly_eligible=True)['dte_eligible']
    assert not check_purchase('2026-10-06',stamp,target=4)['dte_eligible']
    assert check_purchase('2026-10-06',stamp,target=4,weekly_eligible=True)['dte_eligible']
    assert load_scope()['dte_targets']['weekly_subset']==[2,4]


def test_new_feature_scale_and_invalid_range():
    assert dte_fraction('2026-10-07','2026-10-02T15:00:00Z')==1.0
    assert dte_fraction('2026-10-03','2026-10-02T15:00:00Z')==0.2
    with pytest.raises(ValueError):
        dte_fraction('2026-10-08','2026-10-02T15:00:00Z')
