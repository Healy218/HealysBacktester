import numpy as np
import pandas as pd
import pytest

from nn_meta.v7.security_history import security_history,RAW_FIELDS


def fixture():
    days=['2022-03-15','2022-03-16','2022-03-17','2022-03-18']
    opening=pd.to_datetime([d+'T13:30Z' for d in days]).asi8
    clock=pd.DataFrame(dict(source_date=days,session_open_ns=opening,
                            stock_available_ns=opening+390*60*10**9))
    stock=pd.DataFrame(dict(source_date=days,stock_ticker=['OLD','OLD','NEW','NEW'],
        listed_security_id='security',identity_status='dated_identity',identity_evidence_identity='capture',
        observed_minutes=390,session_open_ns=opening,available_ns=clock.stock_available_ns,
        first_observed_ns=pd.array(opening,dtype='Int64'),
        last_observed_ns=pd.array(clock.stock_available_ns-60*10**9,dtype='Int64'),
        raw_open=[100.,101.,102.,103.],raw_high=[100.,101.,102.,103.],
        raw_low=[100.,101.,102.,103.],raw_close=[100.,101.,102.,103.],raw_volume=1000.))
    return stock,clock


def test_rename_stitches_same_identity_and_keeps_each_raw_price_and_timestamp():
    stock,clock=fixture();result=security_history(stock,clock,security_id='security')
    assert result.identity_span.nunique()==1
    assert result.ticker_changed.tolist()==[False,False,True,False]
    assert result.raw_close.tolist()==stock.raw_close.tolist()
    pd.testing.assert_series_equal(result.last_observed_ns,stock.last_observed_ns)
    prefix=security_history(stock.iloc[:2],clock.iloc[:2],security_id='security')
    pd.testing.assert_frame_equal(prefix,result.iloc[:2])


def test_reused_ticker_cannot_pass_as_prior_security():
    stock,clock=fixture();stock.loc[2:,'listed_security_id']='different'
    with pytest.raises(ValueError):security_history(stock,clock,security_id='security')
    result=security_history(stock.iloc[:2],clock,security_id='security')
    assert result.identity_span.iloc[2:].isna().all() and result.raw_close.iloc[2:].isna().all()


def test_multiple_matching_sources_are_not_selected_by_order_or_price():
    stock,clock=fixture();extra=stock.iloc[[2]].copy();extra['stock_ticker']='OTHER'
    extra[list(RAW_FIELDS)]=999.
    result=security_history(pd.concat([stock,extra]),clock,security_id='security')
    assert result.source_status.iloc[2]=='ambiguous_listed_sources'
    assert np.isnan(result.raw_close.iloc[2]) and result.observed_minutes.iloc[2]==0
    assert result.identity_span.iloc[1]!=result.identity_span.iloc[3]
    review=dict(source_date='2022-03-17',stock_ticker='NEW',security_id='security',evidence_identity='dated-alias')
    resolved=security_history(pd.concat([stock,extra]),clock,security_id='security',source_overrides=[review])
    assert resolved.raw_close.tolist()==stock.raw_close.tolist()
    assert resolved.identity_span.nunique()==1 and resolved.listed_source_candidates.iloc[2]==2
    assert resolved.source_selection_evidence.iloc[2]=='dated-alias'
    for wrong in [review|{'stock_ticker':'ABSENT'},review|{'security_id':'other'},review|{'evidence_identity':''}]:
        with pytest.raises(ValueError):
            security_history(pd.concat([stock,extra]),clock,security_id='security',source_overrides=[wrong])


def test_missing_day_breaks_continuity_but_known_halt_keeps_identity():
    stock,clock=fixture();result=security_history(stock.drop(index=1),clock,security_id='security')
    assert len(result)==4 and result.identity_span.iloc[0]!=result.identity_span.iloc[2]
    stock.loc[1,list(RAW_FIELDS)]=np.nan;stock.loc[1,'observed_minutes']=0
    stock.loc[1,['first_observed_ns','last_observed_ns']]=pd.NA
    result=security_history(stock,clock,security_id='security')
    assert result.source_status.iloc[1]=='listed_no_stock_observation'
    assert result.identity_span.nunique()==1


def test_entirely_unknown_history_keeps_calendar_and_stable_nullable_schema():
    import pyarrow as pa
    stock,clock=fixture()
    result=security_history(stock.iloc[:0],clock,security_id='security')
    known=security_history(stock,clock,security_id='security')
    assert len(result)==4 and result.raw_close.isna().all() and result.identity_span.isna().all()
    assert result.observed_minutes.eq(0).all()
    assert pa.Table.from_pandas(result,preserve_index=False).schema.equals(
        pa.Table.from_pandas(known,preserve_index=False).schema)


@pytest.mark.parametrize('change',['duplicate','clock','missing_price','wrong_status'])
def test_invalid_candidate_data_fails(change):
    stock,clock=fixture()
    if change=='duplicate':stock=pd.concat([stock,stock.iloc[:1]])
    if change=='clock':stock.loc[0,'available_ns']+=1
    if change=='missing_price':stock.loc[0,'raw_close']=np.nan
    if change=='wrong_status':stock.loc[0,'identity_status']='missing_composite_figi'
    with pytest.raises(ValueError):security_history(stock,clock,security_id='security')
