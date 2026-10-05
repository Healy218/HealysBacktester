from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from nn_meta.etfe.joined_features import schema,join_batch,validate_bundle,MINUTE
from nn_meta.etfe.joined_pilot import save_bundle,checked_chunk
from nn_meta.etfe.acquisition import digest


def fixture():
    layout=schema();at=pd.Timestamp('2024-01-19T15:00Z').value;m=5;vid='v';g=layout['groups']
    def frame(names,n=1,prefix='diagnostic__'):
        out={}
        for i,name in enumerate(names):
            out[prefix+name]=np.full(n,i+.25,dtype='float64');out['missing__'+prefix+name]=np.zeros(n,dtype='uint8')
            if prefix=='diagnostic__':out['reason__'+name]=['observed_diagnostic']*n
        return pd.DataFrame(out).assign(model_feature_admitted=False)
    events=pd.DataFrame(dict(ticker=['SPY']*3,minutes=[m]*3,variant_id=[vid]*3,strategy=['ma']*3,
        direction=['long']*3,signal_at_ns=[at]*3,target_dte=[0,1,5],raw_spot=[100.]*3,
        acquisition_candidate=[None,'OPT','OPT'],eligibility_reason=['unresolved']*3,
        feature_start_ns=[at-6*MINUTE]*3,feature_end_ns=[at-MINUTE]*3,feature_inside_stock_session=True,entry_eligible=False))
    tech=frame(g['technical'],prefix='raw__');tech['Close']=100.;tech['available_at']=pd.Timestamp(at,tz='UTC');tech['valid']=True;tech.index=[at]
    static=frame(g['static']);static.index=[vid]
    static['diagnostic__strat_ma']=1.;static['diagnostic__timeframe_5']=1.
    daily=frame(g['daily']);daily['available_at']=pd.Timestamp('2024-01-19T14:30Z');daily.index=['2024-01-19']
    signal=frame(g['signal']);signal['variant_id']=vid;signal['strategy']='ma';signal['direction']='long';signal['signal_at_ns']=at;signal['diagnostic__dir_short']=0.
    links=frame(g['identity'],3);links['event_ordinal']=np.arange(3);links['signal_ordinal']=0;links['variant_id']=vid;links['context_session_date']='2024-01-19'
    for n in g['identity']:links['diagnostic__'+n]=np.nan;links['missing__diagnostic__'+n]=np.uint8(1);links['reason__'+n]='dated_identity_unresolved'
    tv=frame(g['tv']);tv['signal_at_ns']=at
    tvlinks=pd.DataFrame(dict(event_ordinal=np.arange(3),observation_ordinal=0,model_feature_admitted=False))
    w=frame(g['option']);w['symbol']='OPT';w['signal_at_ns']=at;w['minutes']=m;w['feature_start_ns']=at-6*MINUTE;w['feature_end_ns']=at-MINUTE;w['inside_stock_session']=True;w.index=['w']
    olinks=pd.DataFrame(dict(event_ordinal=np.arange(3),window_id=[None,'w','w'],model_feature_admitted=False))
    return dict(events=events,technical=tech,static=static,daily=daily,signals=signal,remaining_links=links,tv=tv,tv_links=tvlinks,windows=w,option_links=olinks)


def joined(data=None,start=0,stop=3):return join_batch(fixture() if data is None else data,start,stop,event_sha256='a'*64)


def test_canonical_order_missingness_and_identity():
    b=joined();layout=schema();assert b['matrix'].shape==(3,442)
    assert b['matrix'].columns.tolist()==layout['matrix_columns']
    assert b['rows'].row_id.is_unique and b['rows'].selected_contract.isna().all()
    for n in layout['groups']['option']:
        assert pd.isna(b['matrix'].at[0,n]) and b['matrix'].at[0,'missing__'+n]==1
        assert b['reasons'].at[0,n]=='no_prior_date_observed_candidate' and b['availability'].at[0,n]==-1
        assert b['availability'].at[1,n]==fixture()['events'].feature_end_ns.iloc[1]+1_000_000_000
    assert b['matrix'].at[0,'ma_gap']==fixture()['signals']['diagnostic__ma_gap'].iloc[0]


def test_batch_and_source_order_invariance():
    data=fixture();full=joined(data);parts=[joined(data,0,1),joined(data,1,3)]
    for kind in full:pd.testing.assert_frame_equal(full[kind],pd.concat([p[kind] for p in parts],ignore_index=True),check_exact=True)
    # Source labels are keys; row ordering is not a fallback identity.
    extra=data['static'].copy();extra.index=['other'];extra['diagnostic__strat_ma']=0.
    data['static']=pd.concat([data['static'],extra]).iloc[::-1]
    other_day=data['daily'].copy();other_day.index=['2024-01-18']
    data['daily']=pd.concat([data['daily'],other_day]).iloc[::-1]
    for kind,value in joined(data).items():pd.testing.assert_frame_equal(value,full[kind],check_exact=True)


@pytest.mark.parametrize('source,column,value,message',[
 ('signals','direction','short','Signal identity'),('tv','signal_at_ns',0,'TV clock'),
 ('technical','Close',99.,'Raw spot'),('remaining_links','event_ordinal',7,'ordinal'),
 ('remaining_links','context_session_date','2024-01-18','Context date'),
 ('windows','symbol','OTHER','Option window identity'),('windows','feature_end_ns',1,'Option window identity')])
def test_reject_mismatched_source_identity(source,column,value,message):
    data=fixture();data[source][column]=value
    with pytest.raises(ValueError,match=message):joined(data)


@pytest.mark.parametrize('source',['technical','daily'])
def test_future_context_rejected(source):
    data=fixture();data[source]['available_at']=pd.Timestamp('2024-01-20T00:00Z')
    with pytest.raises(ValueError,match='future|availability'):joined(data)


def test_mask_dtype_duplicate_and_missing_key_rejected():
    for kind in ('mask','dtype','duplicate','missing'):
        data=fixture()
        if kind=='mask':data['signals']['missing__diagnostic__ma_gap']=np.uint8(1)
        elif kind=='dtype':data['signals']['diagnostic__ma_gap']=data['signals']['diagnostic__ma_gap'].astype('float32')
        elif kind=='duplicate':data['static']=pd.concat([data['static'],data['static']])
        else:data['static'].index=['wrong']
        with pytest.raises(ValueError):joined(data)


def test_output_schema_availability_and_admission_rejected():
    for kind in ('order','availability','admission'):
        b=joined()
        if kind=='order':b['matrix']=b['matrix'].iloc[:,::-1]
        elif kind=='availability':b['availability'].iloc[0,0]=b['rows'].signal_at_ns.iloc[0]+1
        else:b['rows']['model_feature_admitted']=True
        with pytest.raises(ValueError):validate_bundle(b['matrix'],b['reasons'],b['availability'],b['rows'])


def test_null_candidate_link_rejected():
    data=fixture();data['option_links'].loc[0,'window_id']='w'
    with pytest.raises(ValueError,match='null mismatch'):joined(data)


def test_checked_resume_rejects_payload_tampering(tmp_path):
    layout=schema();plan=dict(sha256='a'*64,feature_schema=layout,feature_schema_sha256=digest(layout))
    chunk=dict(ticker='SPY',minutes=5,start=0,stop=3);r=save_bundle(tmp_path,chunk,plan,joined())
    assert checked_chunk(tmp_path,chunk,plan)==r
    path=tmp_path/r['files']['matrix']['path'];path.write_bytes(path.read_bytes()+b'bad')
    with pytest.raises(ValueError,match='payload drift'):checked_chunk(tmp_path,chunk,plan)


def test_reason_and_catalog_mismatch_rejected():
    data=fixture();data['signals']['reason__ma_gap']='structural_absence'
    with pytest.raises(ValueError,match='Reason'):joined(data)
    data=fixture();data['static']['diagnostic__strat_ma']=0.
    with pytest.raises(ValueError,match='Catalog family'):joined(data)
