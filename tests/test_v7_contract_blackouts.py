from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.v7.contract_blackouts import (
    BlackoutObservedOptions, BlackoutReferences, BlackoutPolicy,
    ReferenceBlackout, STATUS, compile_blackouts, validate_declaration,
)
from nn_meta.v7.storage import identity, receipt, sha
from options.data.provider import parse_occ_symbol

ROOT = Path(__file__).resolve().parents[1]


def policy_at(tmp_path, contract='OLD220318C00100000', day='2022-03-15'):
    tmp_path.mkdir(parents=True, exist_ok=True)
    doc = json.loads((ROOT/'docs/specs/V7_CONTRACT_REFERENCE_BLACKOUTS_20260927.json').read_text())
    doc['authorization'] = 'Synthetic unit-test fixture only'
    doc['exclusions'] = [dict(contract=contract, date=day)]
    declaration = tmp_path/'policy.json'
    declaration.write_text(json.dumps(doc))
    refs, probes = tmp_path/'missing', tmp_path/'probes'
    source = refs/contract/day
    source.mkdir(parents=True)
    query = dict(path='/v3/reference/options/contracts/O:'+contract, params=dict(as_of=day))
    (source/'response.json').write_text(json.dumps(dict(status='NOT_FOUND')))
    receipt(source, dict(query=query, http_status=404))
    root, expiry, right, strike = parse_occ_symbol(contract)
    for expired in ('false', 'true'):
        probe = probes/contract/expired
        probe.mkdir(parents=True)
        query = dict(path='/v3/reference/options/contracts', params=dict(
            underlying_ticker=root, expiration_date=expiry.isoformat(), strike_price=strike,
            contract_type='call' if right == 'C' else 'put', as_of=day, expired=expired, limit=1000))
        binding = dict(query=query, missing_receipt_sha256=sha(source/'complete.json'))
        (probe/'binding.json').write_text(json.dumps(binding))
        (probe/'response.json').write_text(json.dumps(dict(status='OK', results=[])))
        receipt(probe, dict(http_status=200, pagination_complete=True))
    return compile_blackouts(declaration, refs, probes, tmp_path/'compiled')


def test_exact_contract_date_only_no_new_default_or_replacement(tmp_path):
    policy = policy_at(tmp_path)
    seen = []
    def standard(contract, day):
        seen.append((contract,day))
        return {'parent_result': (contract,day)}
    parent = SimpleNamespace(root=tmp_path, standard=standard)
    guarded = BlackoutReferences(parent, policy)
    for contract in ('OLD220318C00100000', 'O:OLD220318C00100000'):
        with pytest.raises(ReferenceBlackout):
            guarded.standard(contract,'2022-03-15')
    assert seen == []
    for contract,day in [('OLD220318C00100000','2022-03-14'),
                         ('OLD220318C00100000','2022-03-16'),
                         ('OLD220318P00100000','2022-03-15'),
                         ('OLD220318C00101000','2022-03-15')]:
        assert guarded.standard(contract,day) == {'parent_result':(contract,day)}
    assert len(seen) == 4
    with pytest.raises(ReferenceBlackout):
        policy.require_path('OLD220318C00100000',['2022-03-14','2022-03-15','2022-03-16'])
    policy.require_path('OLD220318C00100000',['2022-03-14','2022-03-16'])
    altered = policy.at('OLD220318C00100000','2022-03-15')
    altered['date'] = '2022-03-16'
    assert policy.at('OLD220318C00100000','2022-03-16') is None


def test_policy_rejects_stock_wide_automatic_or_synthetic_calendar_treatment(tmp_path):
    policy = policy_at(tmp_path)
    doc = policy.declaration
    for field in ('automatic_extension','changes_exchange_calendar','rerank_or_replace_contract',
                  'creates_terms_or_outcomes','historically_known_eligibility'):
        with pytest.raises(ValueError, match='finite retrospective'):
            validate_declaration(dict(doc, **{field:True}))
    with pytest.raises(ValueError,match='exact contracts'):
        validate_declaration(dict(doc, exclusions=[dict(symbol='OLD',date='2022-03-15')]))
    with pytest.raises(ValueError,match='Duplicate'):
        validate_declaration(dict(doc, exclusions=doc['exclusions']*2))
    (tmp_path/'policy.json').write_text('{}')
    with pytest.raises(ValueError,match='changed'):
        policy.verify_bindings()
    with pytest.raises(ValueError,match='changed'):
        BlackoutPolicy(tmp_path/'compiled')


def test_alternative_reference_match_cannot_be_blacklisted_as_missing(tmp_path):
    policy = policy_at(tmp_path)
    p=tmp_path/'probes/OLD220318C00100000/false'
    (p/'response.json').write_text(json.dumps(dict(status='OK',results=[dict(ticker='O:OLD220318C00100000')])))
    (p/'complete.json').unlink()
    receipt(p,dict(http_status=200,pagination_complete=True))
    with pytest.raises(ValueError,match='has a match'):
        compile_blackouts(tmp_path/'policy.json',tmp_path/'missing',tmp_path/'probes',tmp_path/'second')
    assert not (tmp_path/'second').exists()


def test_real_assembly_retains_excluded_census_without_features_labels_or_calendar_changes(tmp_path):
    from tests.test_v7_assembly import inputs_at
    from nn_meta.v7.assembly import assemble
    base=tmp_path/'base';base.mkdir()
    join,engine,inputs=inputs_at(base)
    policy=policy_at(tmp_path/'policy')
    guard=BlackoutObservedOptions(engine,policy)
    before=deepcopy(engine.sessions.sessions)
    parent_reference=engine.references
    p=next(p for p in join.proposals.rows() if p['right']=='C')
    result=guard.observe(p,1)
    assert result['status']==STATUS and 'ticks' not in result and 'replay' not in result
    assert result['selection']['status']=='selected' and result['selection']['request_ids']
    assert engine.references is parent_reference and engine.references is not guard.guard
    output=tmp_path/'assembly'
    report=assemble(output,join,guard,inputs=inputs,reserve_bytes=0,proposals_per_chunk=11)
    facts=pd.concat([pd.read_parquet(p/'outcomes.parquet') for p in sorted((output/'chunks').iterdir())])
    assert len(facts)==join.proposals.report['proposals']*5
    excluded=facts[facts.status==STATUS]
    assert len(excluded)>0 and not excluded.feature_complete.any() and not excluded.label_complete.any()
    assert excluded.net_return.isna().all() and excluded.label_end_ns.isna().all()
    assert report['statuses']['no_contract']>0
    assert report['shards']==[]
    assert engine.sessions.sessions==before
    observations=[json.loads(line)['value'] for p in sorted((output/'chunks').iterdir())
                  for line in gzip.open(p/'observations.jsonl.gz','rt')]
    assert any(r.get('admission',{}).get('study_admitted') is False for r in observations)


def test_held_blackout_preserves_open_position_and_never_bridges_it_as_weekend(tmp_path):
    from tests.test_v7_assembly import inputs_at
    base=tmp_path/'base';base.mkdir()
    join,engine,_=inputs_at(base)
    policy=policy_at(tmp_path/'policy',day='2022-03-16')
    original=engine.archive
    # Stable observed fixture marks keep the synthetic position open until the
    # next real session, when the actual reference consumer must hit the guard.
    engine.archive=SimpleNamespace(window=original.window, first_fill=original.first_fill,
        mark=lambda contract,clock:dict(price=1.,bid=.99,ask=1.01,sip_timestamp=clock))
    guarded=BlackoutObservedOptions(engine,policy)
    proposal=next(p for p in join.proposals.rows() if p['right']=='C' and
        pd.Timestamp('2022-03-15T13:50Z').value<=p['decision_ns']<pd.Timestamp('2022-03-15T14:00Z').value)
    proposal=dict(proposal,exit_decision_ns=None)
    result=guarded.observe(proposal,1)
    assert result['status']==STATUS and 'ticks' not in result
    path=result['replay']
    assert len(path['fills'])==1 and path['fills'][0]['side']=='buy'
    assert path['open_positions'] and path['cash']<10000
    assert not path['label_complete'] and path['net_return'] is None and path['label_end_ns'] is None
    assert not path['portfolio_admission'] and not path['study_admitted']
    assert result['admission']['treatments'][0]['date']=='2022-03-16'


def test_earlier_closed_path_is_identical_despite_later_blackout(tmp_path):
    from tests.test_v7_assembly import inputs_at
    base=tmp_path/'base';base.mkdir()
    join,engine,_=inputs_at(base)
    guarded=BlackoutObservedOptions(engine,policy_at(tmp_path/'policy',day='2022-03-16'))
    proposal=next(p for p in join.proposals.rows() if p['right']=='C' and
        pd.Timestamp('2022-03-15T13:50Z').value<=p['decision_ns']<pd.Timestamp('2022-03-15T14:00Z').value)
    before=engine.observe(proposal,1)
    after=guarded.observe(proposal,1)
    assert before['replay']['label_complete'] and after==before


def test_roll_into_blackout_keeps_prior_sale_and_does_not_select_replacement(tmp_path):
    from tests.test_v7_replay import Archive,References,OLD,NEW,ENTRY,ROLL,EXIT
    from nn_meta.v7.replay import replay
    parent=References();parent.root=tmp_path
    references=BlackoutReferences(parent,policy_at(tmp_path/'policy',contract=NEW,day='2022-03-09'))
    selected=[]
    def choose(clock):
        selected.append(clock)
        return OLD if clock<ROLL else NEW
    result=replay(dict(proposal_id='roll',symbol='SPY',right='C',decision_ns=ENTRY,exit_decision_ns=EXIT),
        [ENTRY,ENTRY+60*10**9,ROLL,EXIT],Archive(),references,select_contract=choose,
        expiry_cutoff=lambda c:ROLL if c==OLD else EXIT+86400*10**9,
        session_close=lambda t:t+900*10**9,underlying_mark=lambda s,t:dict(price=400.,sip_timestamp=t))
    assert len(selected)==2
    assert len(result['fills'])==2 and all(f['contract']==OLD for f in result['fills'])
    assert not result['label_complete'] and result['net_return'] is None
    assert references.hits and not result['open_positions']
