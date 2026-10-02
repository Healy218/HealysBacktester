from types import SimpleNamespace
import json
import pandas as pd
import pytest
from scripts.v6_alpaca_market_v1 import AlpacaOptionQuotes

NOW=pd.Timestamp('2026-10-02T18:55:00Z')
SYMBOL='SPY261002C00660000'
class Session:
    def __init__(self,row,status=200):self.row=row;self.status=status;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return SimpleNamespace(status_code=self.status,json=lambda:{'quotes':{SYMBOL:self.row}})
def row(**changes):
    return dict(t=(NOW-pd.Timedelta(seconds=1)).isoformat(),bp=1.0,ap=1.2,bs=10,**{'as':12},**changes)
def test_fresh_quote_preserves_provenance(tmp_path):
    s=Session(row());m=AlpacaOptionQuotes(tmp_path,session=s,clock=lambda:NOW)
    q=m.execution_quote(SYMBOL,after=NOW-pd.Timedelta(seconds=30))
    assert q['provider']=='alpaca' and q['feed']=='opra'
    assert q['sip_timestamp_ns']==NOW.value-1_000_000_000
    assert s.calls[0][1]['params']['feed']=='opra'
    assert 'alpaca.markets' in s.calls[0][0]
    assert json.loads(open(q['receipt']['path']).read())['raw_quote']==s.row
@pytest.mark.parametrize('offset,after',[(31,60),(-1,60),(10,5)])
def test_stale_future_and_predecision_quotes_rejected(tmp_path,offset,after):
    r=row();r['t']=(NOW-pd.Timedelta(seconds=offset)).isoformat()
    m=AlpacaOptionQuotes(tmp_path,session=Session(r),clock=lambda:NOW)
    with pytest.raises(ValueError,match='no fresh'):
        m.execution_quote(SYMBOL,after=NOW-pd.Timedelta(seconds=after))
@pytest.mark.parametrize('field,value',[('bp',0),('ap',.5),('bs',0),('as',float('nan'))])
def test_invalid_markets_rejected(tmp_path,field,value):
    r=row();r[field]=value
    m=AlpacaOptionQuotes(tmp_path,session=Session(r),clock=lambda:NOW)
    with pytest.raises(ValueError,match='invalid'):
        m.execution_quote(SYMBOL,after=NOW-pd.Timedelta(seconds=30))
def test_no_indicative_fallback_on_entitlement_error(tmp_path):
    s=Session(row(),403);m=AlpacaOptionQuotes(tmp_path,session=s,clock=lambda:NOW)
    with pytest.raises(RuntimeError,match='HTTP 403'):
        m.execution_quote(SYMBOL,after=NOW-pd.Timedelta(seconds=30))
    assert len(s.calls)==1

def test_feature_windows_cannot_be_filled_with_latest_quote(tmp_path):
    from scripts.v6_alpaca_market_v1 import AlpacaRecordedMarket
    m=AlpacaRecordedMarket(tmp_path,session=Session(row()),clock=lambda:NOW)
    with pytest.raises(ValueError,match='not admitted'):m.tick_features({'contract':SYMBOL},{})
    assert not m.session.calls

def test_missing_catalogue_cannot_fall_back_to_massive(tmp_path):
    from scripts.v6_alpaca_market_v1 import AlpacaRecordedMarket
    from datetime import date
    m=AlpacaRecordedMarket(tmp_path,session=Session(row()),clock=lambda:NOW)
    with pytest.raises(ValueError,match='catalogue unavailable'):
        m.get_chain('SPY',right='C',expiration_gte=date(2026,10,3),expiration_lte=date(2026,11,3),as_of=date(2026,10,1))
    assert not m.session.calls
