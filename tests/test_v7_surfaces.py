import numpy as np
import pandas as pd
import pytest
from nn_meta.v7.daily import surface_day
from nn_meta.v7.surfaces import surface_panel


def fixtures():
    stocks=pd.DataFrame(dict(stock_ticker=['SPY','ABC','ZERO','EMPTY','NONE'],raw_close=[420.,100.,np.nan,50.,25.],observed_minutes=[390,210,0,390,390]))
    options=pd.DataFrame(dict(ticker=['O:SPY220318C00420000','O:SPY220429C00420000','O:SPY220318P00420000',
        'O:ABC220318C00100000','O:ABC220429P00100000','O:ZERO220318C00010000',
        'O:EMPTY220315C00050000','O:EMPTY220318C00050000','O:SPY220318C00500000'],
        close=[3.,10.,3.,2.,5.,1.,3.,.01,1.],volume=[100.,100.,50.,10.,20.,40.,50.,1.,30.]))
    return stocks,options


def test_vectorized_panel_matches_existing_scalar_proxy_for_every_observed_root():
    stocks,options=fixtures();panel=surface_panel('2022-03-15',stocks,options).set_index('stock_ticker')
    for stock in stocks[stocks.observed_minutes.gt(0)].itertuples():
        expected=surface_day(stock.stock_ticker,'2022-03-15',options,stock.raw_close)
        for key in ['atm_iv_near','atm_iv_far','pc_ratio','option_contract_observations']:
            assert panel.loc[stock.stock_ticker,key]==pytest.approx(expected[key],nan_ok=True)
    assert panel.loc['ZERO','surface_status']=='no_stock_observation'
    assert pd.isna(panel.loc['ZERO','atm_iv_near'])
    assert panel.loc['EMPTY','surface_status']=='no_admitted_tenor_premium'
    assert panel.loc['NONE','surface_status']=='no_option_observation'
    assert panel.capture_complete.all() and not panel.loc['ZERO','stock_observed']
    assert panel.loc['SPY','option_contract_observations']==4
    assert panel.loc['SPY','near_iv_observations']==2


def test_empty_option_capture_preserves_explicit_absence():
    stocks,options=fixtures();result=surface_panel('2022-03-15',stocks,options.iloc[:0])
    assert len(result)==len(stocks) and result.option_contract_observations.eq(0).all()
    assert result[['atm_iv_near','atm_iv_far','pc_ratio']].isna().all().all()
    assert result.capture_complete.all()


def test_bad_inputs_duplicates_ambiguous_roots_and_missing_spot_are_rejected():
    stocks,options=fixtures()
    with pytest.raises(ValueError,match='duplicate'):
        surface_panel('2022-03-15',stocks,pd.concat([options,options.iloc[:1]]))
    bad=stocks.copy();bad.loc[0,'raw_close']=np.nan
    with pytest.raises(ValueError,match='disagree'):surface_panel('2022-03-15',bad,options)
    bad=stocks.copy();bad.loc[2,'raw_close']=10.
    with pytest.raises(ValueError,match='disagree'):surface_panel('2022-03-15',bad,options)
    bad=stocks.copy();bad.loc[0,'stock_ticker']='AB.C';bad.loc[1,'stock_ticker']='ABC'
    with pytest.raises(ValueError,match='Ambiguous'):surface_panel('2022-03-15',bad,options)
    bad=options.copy();bad.loc[0,'volume']=-1
    with pytest.raises(ValueError,match='Invalid'):surface_panel('2022-03-15',stocks,bad)


def test_over_ceiling_premiums_do_not_saturate_to_a_fake_five_hundred_percent_iv():
    stocks,options=fixtures();options.loc[0,'close']=100000
    result=surface_panel('2022-03-15',stocks,options).set_index('stock_ticker')
    assert result.loc['SPY','near_iv_observations']==1
    row=surface_day('SPY','2022-03-15',options,420.)
    assert result.loc['SPY','atm_iv_near']==pytest.approx(row['atm_iv_near'])


def surface_store(tmp_path):
    import json
    from nn_meta.v7.storage import receipt, sha, identity
    from scripts.build_v7_surfaces import save
    stocks, options = fixtures()
    stocks['source_date'] = '2022-03-15'
    stocks['available_ns'] = pd.Timestamp('2022-03-15T20:00Z').value
    shard = tmp_path/'stock/shards/one'; shard.mkdir(parents=True)
    stocks.to_parquet(shard/'daily.parquet', index=False)
    receipt(shard, {})
    parent = tmp_path/'parent.json'; parent.write_text('{}')
    binding = dict(declaration=dict(inputs={str(parent):sha(parent)},sources={}),
                   shards={str(shard/'complete.json'):sha(shard/'complete.json')})
    summary = tmp_path/'stock/summary'; summary.mkdir()
    save(summary/'binding.json', binding)
    save(summary/'report.json', dict(raw_calendar_rows=len(stocks)))
    receipt(summary, dict(identity=identity(binding)))
    raw = tmp_path/'source/options/day_aggs/2022-03-15'; raw.mkdir(parents=True)
    (raw/'raw.csv').write_text('captured raw daily options fixture\n')
    task=dict(key='options/day_aggs/2022-03-15',kind='day_aggs',
              object='us_options_opra/day_aggs_v1/2022/03/2022-03-15.csv.gz')
    receipt(raw,dict(task=task))
    audit=tmp_path/'audit/options/2022-03-15'; audit.mkdir(parents=True)
    options.to_parquet(audit/'contracts.parquet',index=False)
    save(audit/'summary.json',dict(input_receipt_sha256=sha(raw/'complete.json')))
    receipt(audit,dict(kind='options',key='2022-03-15'))
    return tmp_path/'stock',tmp_path/'source',tmp_path/'audit'


def test_whole_day_builder_immutable_resume_availability_and_source_mutation(tmp_path,monkeypatch):
    from scripts import build_v7_surfaces as builder
    from nn_meta.v7.storage import sha, verify
    monkeypatch.setattr('scripts.download_v7_data.disk_guard',lambda *args:None)
    stock, source, audit = surface_store(tmp_path)
    index=tmp_path/'index'; output=tmp_path/'days';output.mkdir()
    builder.prepare_spots(stock,index)
    digest=sha(index/'complete.json');builder.prepare_spots(stock,index)
    assert sha(index/'complete.json')==digest
    opening=pd.Timestamp('2022-03-16T13:30Z').value
    task=('2022-03-15',index,source,audit,output,opening,builder.sources())
    builder.work(task)
    frame=pd.read_parquet(output/'2022-03-15/surfaces.parquet')
    assert len(frame)==5 and frame.available_ns.eq(opening).all()
    assert frame.stock_available_ns.lt(frame.available_ns).all()
    assert frame.set_index('stock_ticker').loc['ZERO','surface_status']=='no_stock_observation'
    digest=sha(output/'2022-03-15/complete.json');builder.work(task)
    assert sha(output/'2022-03-15/complete.json')==digest
    verify(output/'2022-03-15')
    with pytest.raises(ValueError,match='identity mismatch'):
        builder.work((*task[:5],opening+1,task[-1]))
    (source/'options/day_aggs/2022-03-15/raw.csv').write_text('changed')
    with pytest.raises(RuntimeError,match='hash mismatch'):builder.work(task)


def test_daily_parent_lineage_mismatch_and_unsealed_changes_are_rejected(tmp_path,monkeypatch):
    from scripts import build_v7_surfaces as builder
    from nn_meta.v7.storage import receipt
    monkeypatch.setattr('scripts.download_v7_data.disk_guard',lambda *args:None)
    stock,source,audit=surface_store(tmp_path)
    index=tmp_path/'index';builder.prepare_spots(stock,index)
    (tmp_path/'parent.json').write_text('changed')
    with pytest.raises(ValueError,match='parent input'):builder.prepare_spots(stock,index)
    (audit/'options/2022-03-15/summary.json').write_text('{"input_receipt_sha256":"wrong"}')
    # Resealing a changed audit still cannot make it belong to this raw capture.
    (audit/'options/2022-03-15/complete.json').unlink()
    receipt(audit/'options/2022-03-15',dict(kind='options',key='2022-03-15'))
    task=('2022-03-15',index,source,audit,tmp_path/'days',pd.Timestamp('2022-03-16T13:30Z').value,builder.sources())
    with pytest.raises(ValueError,match='lineage differs'):builder.work(task)


def test_extended_calendar_requires_raw_equality_and_unchanged_overlap(tmp_path):
    import json
    from nn_meta.v7.storage import receipt
    from scripts.build_v7_surfaces import availability_calendar
    original=dict(coverage_start='2022-03-15',coverage_end='2022-03-15',
                  sessions=[dict(date='2022-03-15',open='09:30',close='16:00')])
    old=tmp_path/'old.json';old.write_text(json.dumps(original))
    extra=tmp_path/'extra';extra.mkdir()
    extended={**original,'provider':'alpaca_calendar','coverage_end':'2022-03-16',
              'sessions':original['sessions']+[dict(date='2022-03-16',open='09:30',close='16:00')]}
    def seal():
        (extra/'calendar.json').write_text(json.dumps(extended))
        (extra/'calendar.raw.json').write_text(json.dumps(extended['sessions']))
        (extra/'complete.json').unlink(missing_ok=True)
        receipt(extra,{})
    seal()
    assert '2022-03-16' in availability_calendar(old,extra).sessions
    extended['sessions'][0]['close']='13:00';seal()
    with pytest.raises(ValueError,match='disagrees'):availability_calendar(old,extra)
    extended['sessions'][0]['close']='16:00';seal()
    (extra/'calendar.raw.json').write_text('[]')
    (extra/'complete.json').unlink();receipt(extra,{})
    with pytest.raises(ValueError,match='records required'):availability_calendar(old,extra)
