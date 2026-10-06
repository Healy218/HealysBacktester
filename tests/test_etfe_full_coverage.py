import json
from pathlib import Path
import pytest
from nn_meta.etfe import full_coverage as c, full_discovery as f, demand as d


def raw(**changes):
    return dict(dict(symbol='SPY240119C00400000',underlying_symbol='SPY',expiration_date='2024-01-19',
        status='active',id='native',underlying_asset_id='etf',type='call',strike_price='400',
        multiplier='0',size='100',deliverables=[dict(settlement_type='T+1')],
        close_price_date='2024-01-19',open_interest_date='2024-01-18'),**changes)


def test_observation_dates_and_positive_size_cannot_admit_terms():
    reasons=c.dated_reasons(raw())
    assert 'terms_available_at_absent' in reasons
    assert 'terms_effective_at_absent' in reasons
    assert 'nonpositive_or_invalid_raw_multiplier' in reasons
    assert 'current_T1_delivery_on_pre_transition_expiry' in reasons


def test_unverified_extra_clocks_never_promote_current_snapshot():
    reasons=c.dated_reasons(raw(effective_at='2023-01-01',available_at='2023-01-01',multiplier='100'))
    assert 'current_snapshot_not_dated_contract_terms' in reasons
    assert 'terms_available_at_absent' not in reasons


@pytest.mark.parametrize('expiry,flag',[('2024-05-27',True),('2024-05-28',False)])
def test_settlement_transition_flag_is_dated(expiry,flag):
    assert ('current_T1_delivery_on_pre_transition_expiry' in c.dated_reasons(raw(expiration_date=expiry)))==flag


@pytest.mark.parametrize('symbol',['SPY240119C00400000','1SPY240119C00400000'])
def test_complete_ranges_cover_empty_exact_queries_without_historical_admission(tmp_path,monkeypatch,symbol):
    root=tmp_path/'audit';root.mkdir()
    source=tmp_path/'raw';plan=f.prepare(source,f.full_jobs())
    class HTTP:
        def get(self,route,params,cap):
            records=[raw(symbol=symbol)] if params['underlying_symbols']=='SPY' and params['status']=='active' else []
            return 200,json.dumps(dict(option_contracts=records,next_page_token=None)).encode(),{},None
    f.capture(source,HTTP(),sleep=lambda _:None,check_resources=lambda *_:None)
    prior=tmp_path/'prior';prior.mkdir();(prior/'FRONTIER.json').write_text(json.dumps(dict(inputs=[])))
    calendar=[dict(date='2024-01-18',open='09:30',close='16:00')]
    _,queries=d.calendar_demand(calendar)
    manifest=dict(raw_root=str(source),raw_plan_sha256=plan['sha256'],calendar_root='calendar',
        frontier_root=str(prior),inventory_root='inventory',sha256='manifest')
    monkeypatch.setattr(c,'load',lambda _:manifest)
    monkeypatch.setattr(c,'read_calendar',lambda _:calendar)
    monkeypatch.setattr(c,'load_inventory',lambda _:dict(queries={k:dict(item=v) for k,v in queries.items()}))
    monkeypatch.setattr(f,'guard',lambda *_:None)
    result=c.run(root)
    assert result['summary']['calendar_transport_complete']==276
    assert result['summary']['historical_complete_queries']==0
    assert result['summary']['returned_occurrences']==1
    assert result['summary']['purchase_symbol_session_edges']==1
    assert result['dated_terms_admitted']==0 and not result['ready_for_build']
    assert sum(e['returned_occurrences']==0 for e in result['exact_queries'])==275
    from scripts import verify_etfe_full_coverage as independent
    monkeypatch.setattr(independent,'load',lambda _:manifest)
    monkeypatch.setattr(independent,'read_calendar',lambda _:calendar)
    monkeypatch.setattr(independent,'load_inventory',lambda _:dict(queries={k:dict(item=v) for k,v in queries.items()}))
    assert independent.audit(root)['raw_typed_occurrences_reconciled']
    before={p.name:p.read_bytes() for p in (root/'partitions').glob('*')}
    assert c.run(root)==result
    assert all((root/'partitions'/n).read_bytes()==v for n,v in before.items())
    next((root/'partitions').glob('*.parquet')).write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='payload changed'): c.run(root)
