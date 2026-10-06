import pandas as pd
import pytest

from nn_meta.etfe import closing_reference as c, stock_trade_capture as t


def trade(p,s,x,cond):
    return dict(t='2025-06-13T20:00:00.3Z',p=p,s=s,x=x,c=cond,i=1,z='B')


def test_official_close_uses_listing_venue_only():
    rows=[trade(596.96,200,'T',[' ','M']),trade(597.0,1978583,'P',[' ','6']),trade(597.0,1978583,'P',[' ','M'])]
    assert c.official_close('SPY',rows)==dict(status='resolved',price=597.0,reason='official_close')
    assert c.official_close('QQQ',rows)['status']=='missing'


def test_official_close_flags_conflicts():
    assert c.official_close('SPY',[trade(1.0,1,'P',['M']),trade(1.1,1,'P',['M'])])['reason']=='conflicting_official_close'
    assert c.official_close('SPY',[trade(1.0,1,'P',['M']),trade(1.1,1,'P',['6'])])['reason']=='closing_print_disagrees'
    assert c.official_close('VOO',[trade(1.0,1,'P',['M'])])['reason']=='official_close_without_closing_print'


def test_exercise_threshold_is_exact_cents():
    assert c.exercise_outcome('C',597.00,597.01)['exercised']
    assert not c.exercise_outcome('C',597.00,597.00)['exercised']
    assert c.exercise_outcome('P',600.0,599.99)['exercised']
    assert c.exercise_outcome('P',600.0,599.99)['pin'] and not c.exercise_outcome('P',600.0,599.9)['pin']
    assert c.exercise_outcome('C',500.0,503.25)['intrinsic']==pytest.approx(3.25)


def test_trade_job_bounds():
    close=pd.Timestamp('2025-06-13 16:00',tz='America/New_York').tz_convert('UTC')
    j=c.window_job('SPY',close)
    assert j['params']['start']=='2025-06-13T19:59:55+00:00' and j['params']['end']=='2025-06-13T20:00:30+00:00'
    with pytest.raises(ValueError):t.job('stock_trades',dict(j['params'],symbols='IWM'),'x')
    with pytest.raises(ValueError):t.job('stock_trades',dict(j['params'],end='2025-06-13T20:05:00+00:00'),'x')


def test_v2_falls_back_to_listing_closing_cross_and_nasdaq_alias():
    from nn_meta.etfe import exercise_reference as x
    six_only=[trade(590.5,671315,'P',[' ','6']),trade(590.48,4000,'T',[' '])]
    assert x.official_close('SPY',six_only)==dict(status='resolved',price=590.5,reason='closing_print_without_official_close')
    nasdaq_t=[trade(503.17,241287,'T',['@','6','X'])]
    assert x.official_close('QQQ',nasdaq_t)['price']==503.17
    assert x.official_close('SPY',nasdaq_t)['status']=='missing'
    assert x.official_close('SPY',[trade(1.0,1,'P',['6']),trade(1.1,1,'P',['6'])])['reason']=='conflicting_closing_print'
