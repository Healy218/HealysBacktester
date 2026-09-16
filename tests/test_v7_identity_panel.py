import pandas as pd
import pytest
from nn_meta.v7.identity_panel import attach_day,continuity_spans


def test_literal_and_punctuation_mapping_unknown_and_collision():
    stock=pd.DataFrame(dict(stock_ticker=['ABC','BRKB','NONE','MISS','TWIN'],source_date='2022-03-15'))
    rows=[dict(ticker=t,composite_figi=i,primary_exchange='XNYS',type='CS') for t,i in
          [('ABC','a'),('BRK.B','b'),('MISS',None),('TWIN','c'),('TWIN','d')]]
    result=attach_day(stock,rows,day='2022-03-15',evidence_identity='source')
    assert result.listed_security_id.tolist()==['a','b',None,None,None]
    assert result.identity_status.tolist()==['dated_identity','dated_identity','absent_from_listed_capture',
                                           'missing_composite_figi','ambiguous_listed_symbol']


def test_no_forward_fill_or_bridge_missing_calendar_day_or_changed_id():
    days=pd.bdate_range('2022-03-15',periods=8).strftime('%Y-%m-%d').tolist()
    panel=pd.DataFrame(dict(stock_ticker='ABC',source_date=[d for i,d in enumerate(days) if i!=5],
        listed_security_id=['a','a',None,'a','b','b','b']))
    result=continuity_spans(panel,days)
    spans=result.identity_span.tolist()
    assert spans[0]==spans[1]
    assert spans[2] is None
    assert len({spans[0],spans[3],spans[4],spans[5]})==4
    assert spans[5]==spans[6]
    prefix=continuity_spans(panel.iloc[:4],days)
    pd.testing.assert_frame_equal(prefix,result.iloc[:4])
    nullable=panel.copy()
    nullable['listed_security_id']=nullable.listed_security_id.astype('string')
    assert continuity_spans(nullable,days).identity_span.tolist()==spans


def test_unordered_and_duplicate_inputs_fail_or_sort_explicitly():
    panel=pd.DataFrame(dict(stock_ticker=['ABC','ABC'],source_date=['2022-03-15']*2,listed_security_id=['a']*2))
    with pytest.raises(ValueError):continuity_spans(panel,['2022-03-15'])
    with pytest.raises(ValueError):attach_day(panel,[],day='2022-03-15',evidence_identity='source')
    with pytest.raises(ValueError):continuity_spans(panel.iloc[:1],['2022-03-16'])
