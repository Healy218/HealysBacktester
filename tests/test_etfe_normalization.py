import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pytest

from nn_meta.etfe import normalization as n
from nn_meta.etfe.acquisition import capture,job,prepare,save,sha,write_new
from scripts.acquire_etfe_alpaca import interval


class HTTP:
    def __init__(self,bodies):self.bodies=iter(bodies)
    def get(self,*args):return 200,json.dumps(next(self.bodies)).encode(),{},None


def calendar(root):
    root.mkdir()
    body=[dict(date='2024-01-18',open='09:30',close='16:00'),
          dict(date='2024-11-29',open='09:30',close='13:00'),
          dict(date='2026-10-02',open='09:30',close='16:00')]
    write_new(root/'000-calendar.body',json.dumps(body).encode())
    save(root/'000-calendar.json',dict(status_code=200,params={'start':'2024-01-01','end':'2026-10-02'},
        body_path='000-calendar.body',body_sha256=sha((root/'000-calendar.body').read_bytes())))
    save(root/'CALENDAR.json',dict(files={p.name:sha(p.read_bytes()) for p in root.iterdir()}))
    return root


def bar(t='2024-01-18T14:30:00Z',close=1.0):
    return dict(t=t,o=1.,h=max(1.,close),l=min(1.,close),c=close,v=10,n=2,vw=1.)


def raw_root(root):
    jobs=[job('stock_bars',dict(symbols='SPY',timeframe='1Min',feed='sip',adjustment='raw',asof='-',
            sort='asc',limit=10000,**interval('2024-01-18','2024-01-19')),'stock'),
        job('option_trades',dict(symbols='SPY240118C00475000',sort='asc',limit=10000,
            **interval('2024-01-18','2024-01-19')),'trades')]
    prepare(root,jobs)
    trade=dict(t='2024-01-18T14:30:00.009729024Z',p=1.13,s=3,c='I',x='X')
    data=[dict(bars={'SPY':[bar(),bar(),bar(close=1.2),bar('2024-01-18T21:00:00Z')]},next_page_token=None),
          dict(trades={'SPY240118C00475000':[trade,trade]},next_page_token=None)]
    capture(root,HTTP(data),sleep=lambda _:None,check_resources=lambda *_:None)
    return root


def test_parquet_lossless_occurrences_session_gaps_and_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(n,'storage_guard',lambda *_:None)
    raw=raw_root(tmp_path/'raw');cal=calendar(tmp_path/'calendar');out=tmp_path/'normalized'
    n.prepare_normalization(out,[raw],cal)
    first=n.normalize(out,max_partitions=1)
    assert not first['normalized_complete']
    receipt=next((out/'partitions').glob('*.json'));before=receipt.read_bytes()
    final=n.normalize(out)
    assert final['normalized_complete'] and final['rows']==6
    assert receipt.read_bytes()==before
    parts=[json.loads(p.read_text()) for p in (out/'partitions').glob('*.json')]
    stock=next(p for p in parts if p['route']=='stock_bars')
    assert stock['quality_counts']=={'duplicate_bar_identical':1,'duplicate_bar_conflicting':1}
    assert stock['session_counts']=={'stock_regular':3,'outside_stock_regular':1}
    gap=stock['stock_session_coverage'][0]
    assert (gap['expected_minutes'],gap['observed_minutes'],gap['missing_minutes'])==(390,1,389)
    assert gap['valid_price_minutes']==0 and gap['invalid_observed_minutes']==1
    assert gap['missing_classification']=='unresolved_provider_gap_or_no_trade'
    trades=next(p for p in parts if p['route']=='option_trades')
    table=pq.read_table(out/trades['data']).to_pylist()
    assert table[0]['timestamp_ns']==1705588200009729024
    assert table[0]['calendar_dte']==0 and table[0]['native_trade_id'] is None
    assert table[0]['raw_json']==table[1]['raw_json']
    assert table[0]['occurrence_id']!=table[1]['occurrence_id']
    assert trades['identical_trade_content_occurrences_retained']==1
    assert n.normalize(out)['processed_this_run']==0


def test_bad_numeric_values_are_flagged_and_raw_retained():
    raw=dict(t='2024-01-18T14:30:00Z',p='NaN',s=1.5,c='K',x='X')
    result=n.typed_row('SPY240118C00475000',raw,route='option_trades',plan_sha='p',job_id='j',
        page=0,ordinal=0,receipt={'body_sha256':'b','received_at':'2026-10-04T00:00:00Z'},sessions={})
    assert result['price'] is None and result['size'] is None
    assert set(result['quality_flags'])=={'invalid_price','invalid_size','unmapped_trade_condition'}
    assert json.loads(result['raw_json'])==raw


def test_early_close_and_stock_hours_do_not_claim_option_hours():
    sessions=n.session_map([dict(date='2024-11-29',open='09:30',close='13:00')])
    item={'route':'stock_bars','params':interval('2024-11-29','2024-11-30')}
    gaps=n.stock_gaps(item,sessions,{},{});assert gaps[0]['expected_minutes']==210
    raw=bar('2024-11-29T18:05:00Z')
    row=n.typed_row('SPY241129C00600000',raw,route='option_bars',plan_sha='p',job_id='j',page=0,
        ordinal=0,receipt={'body_sha256':'b','received_at':'2026-10-04T00:00:00Z'},sessions=sessions)
    assert row['stock_session']=='outside_stock_regular'
    assert row['quality_flags']==[]


def test_corrupt_output_fails_before_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(n,'storage_guard',lambda *_:None)
    raw=raw_root(tmp_path/'raw');cal=calendar(tmp_path/'calendar');out=tmp_path/'normalized'
    n.prepare_normalization(out,[raw],cal);n.normalize(out)
    receipt=json.loads(next((out/'partitions').glob('*.json')).read_text())
    (out/receipt['data']).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):n.normalize(out)


def test_calendar_tamper_fails(tmp_path,monkeypatch):
    monkeypatch.setattr(n,'storage_guard',lambda *_:None)
    raw=raw_root(tmp_path/'raw');cal=calendar(tmp_path/'calendar');out=tmp_path/'normalized'
    n.prepare_normalization(out,[raw],cal)
    (cal/'000-calendar.body').write_text('[]')
    with pytest.raises(ValueError,match='Calendar checksum'):n.normalize(out)
