import json
from pathlib import Path

import pytest

from nn_meta.etfe import demand as d
from nn_meta.etfe.acquisition import capture,prepare


class Fake:
    def __init__(self,body):self.body=body
    def get(self,*args):return 200,json.dumps(self.body).encode(),{},None


def captured(root,item,body):
    prepare(root,[item])
    r=capture(root,Fake(body),sleep=lambda _:None,check_resources=lambda *_:None)
    assert r['capture_complete']


def test_calendar_demand_includes_zero_weekends_and_beyond_fixed_end():
    edges,queries=d.calendar_demand([dict(date='2026-10-02'),dict(date='2026-10-05')])
    assert len(edges)==6
    first=edges[0]['expiries']
    assert first[0]['purposes']==['purchase_discovery']
    assert first[5]['purposes']==['purchase_discovery','daily_context']
    assert first[6]['purposes']==['daily_context']
    assert first[1]['expiry']=='2026-10-03'  # Saturday is not silently excluded
    assert first[45]['expiry']=='2026-11-16'
    assert len(queries)==49*3*2  # three overlapping days factored once
    assert all(q['params'].get('type') is None for q in queries.values())


def test_january_reuses_query_across_purpose_labels():
    item=d.discovery_job('SPY','2024-01-19','inactive');key=d.query_key(item)
    different=dict(item,purpose='old_transport')
    assert d.query_key(different)==key
    jobs,details=d.january_discovery(dict(queries={key:dict(disposition='captured',capture=dict(job_id='old'))}))
    assert len(jobs)==64*6-1
    assert details['reused_discovery']==[dict(job_id='old')]
    assert any(j['params']['expiration_date']=='2024-01-06' for j in jobs)


def test_reuse_requires_complete_uncorrupted_pages(tmp_path):
    item=d.discovery_job('SPY','2024-01-19','inactive');root=tmp_path/'raw'
    prepare(root,[item])
    with pytest.raises(ValueError,match='complete'):d.verified_inputs([root])
    capture(root,Fake(dict(option_contracts=[],next_page_token=None)),
            sleep=lambda _:None,check_resources=lambda *_:None)
    _,inventory=d.verified_inputs([root])
    assert d.query_key(item) in inventory  # transport complete, not no-trade
    next((root/'attempts').glob('*/body.json')).write_text('{}')
    with pytest.raises(ValueError,match='checksum'):d.verified_inputs([root])


def test_duplicate_query_vintages_not_implicitly_selected(tmp_path):
    item=d.discovery_job('SPY','2024-01-19','inactive')
    a,b=tmp_path/'a',tmp_path/'b'
    captured(a,item,dict(option_contracts=[],next_page_token=None))
    other=dict(item,purpose='other')
    from nn_meta.etfe.acquisition import job
    other=job(other['route'],other['params'],other['purpose'])
    captured(b,other,dict(option_contracts=[],next_page_token=None))
    with pytest.raises(ValueError,match='vintages'):d.verified_inputs([a,b])


def test_incomplete_discovery_grid_cannot_claim_surface(tmp_path):
    root=tmp_path/'raw';item=d.discovery_job('SPY','2024-01-19','inactive')
    captured(root,item,dict(option_contracts=[],next_page_token=None))
    with pytest.raises(ValueError,match='grid'):d.returned_contracts([root])


def test_full_surface_batches_all_strikes_and_links_reused_windows(monkeypatch):
    contracts={f'SPY240119C{strike:08}':dict(ticker='SPY',expiry='2024-01-19',source={})
               for strike in range(100000,100202)}
    symbol=next(iter(contracts))
    existing=d.bars_job([symbol],'2024-01-18','2024-01-19','bootstrap')
    monkeypatch.setattr(d,'returned_contracts',lambda _: ([],contracts,{'old':dict(item=existing)}))
    jobs,meta=d.january_bars([], 'surfaces', [dict(date='2024-01-18'),dict(date='2024-01-19')])
    assert len(jobs)==6 and len(meta['reused_symbol_windows'])==1
    assert len(meta['symbol_window_edges'])==404
    assert all(len(j['params']['symbols'].split(','))<=100 for j in jobs)
    assert sum(len(j['params']['symbols'].split(',')) for j in jobs)==403
    assert sum(e['purposes']==['purchase_discovery'] for e in meta['symbol_window_edges'])==202
    assert all(e.get('job_id') or e['capture'] for e in meta['symbol_window_edges'])


def test_boundary_is_nonoverlapping_and_includes_later_expiries(monkeypatch):
    contracts={'VOO240301P00400000':dict(ticker='VOO',expiry='2024-03-01',source={})}
    monkeypatch.setattr(d,'returned_contracts',lambda _: ([],contracts,{}))
    jobs,meta=d.january_bars([], 'boundary', [dict(date='2024-01-02'),dict(date='2024-01-03')])
    assert jobs[0]['params']['end']=='2024-01-18T04:59:59.999999999+00:00'
    assert meta['regular_minute_scenario_rows']==780
    assert meta['symbol_window_edges'][0]['purposes']==['history_diagnostic']


def test_surface_excludes_outside_45_dte_without_excluding_0dte(monkeypatch):
    contracts={'SPY240118C00400000':dict(ticker='SPY',expiry='2024-01-18',source={}),
               'SPY240304P00400000':dict(ticker='SPY',expiry='2024-03-04',source={})}
    monkeypatch.setattr(d,'returned_contracts',lambda _: ([],contracts,{}))
    jobs,meta=d.january_bars([], 'surfaces', [])
    assert [(e['day'],e['purposes']) for e in meta['symbol_window_edges']]==[
        ('2024-01-18',['purchase_discovery']),('2024-01-19',['daily_context'])]
