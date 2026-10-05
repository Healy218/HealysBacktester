from copy import deepcopy
import json
from pathlib import Path

import pytest

from nn_meta.etfe.integration_ledger import Scheduler, SharedLedger, BASELINE, stress_profiles, stressed_bars


def quote(at, bid=200, symbol='SPY', size=1000):
    return dict(t=at,available_at=at,bid=bid,ask=bid+.2,bid_size=size,ask_size=size,
                feed='sip',symbol=symbol,id=at,size_to_shares=1)


def bar(at,price=2,volume=1000,count=10):
    return dict(t=at,vw=price,v=volume,n=count)


def tape():
    root=Path(__file__).resolve().parents[1]
    seed=json.loads((root/'docs/specs/ETFE_EXPIRY_HAND_FIXTURES_20261005.json').read_text())['cases'][0]
    base,life=seed['base'],seed['lifecycle']
    # Miniature synthetic sessions make event completeness inspectable; no real calendar claim.
    for group in (base['sessions'],life['stock_sessions']):
        for sessions in group.values():
            for day in sessions:sessions[day]=[day+'T13:30:00Z',day+'T14:00:00Z']
    for terms in base['contracts'].values():terms['expiry_close']=terms['expiration_date']+'T14:00:00Z'
    p=dict(id='one',symbol='SPY',right='C',target=0,variant='alpha',qualifies=True,signal_at='2024-05-24T13:31:00Z')
    return dict(evidence_kind='synthetic',start='2024-05-24T13:30:00Z',end='2024-05-28T13:30:02Z',
        base=base,lifecycle=life,proposals=[p],coverage={'A':True,'B':True,'N':True,'SPY':True,'QQQ':True,'VOO':True},
        bars={'A':[bar('2024-05-24T13:30:00Z'),bar('2024-05-24T13:31:00Z',2.1)]},
        quotes={'SPY':[quote('2024-05-24T13:31:00Z')]},exercises={},
        strategy_exits=[dict(at='2024-05-24T13:32:01Z',proposal_id='one')])


def test_auto_entry_exit_settlement_and_horizon_hand_arithmetic():
    sim=Scheduler(tape());out=sim.run()
    assert out['complete'] and out['registered_count']==1
    # 10 * 200.30 debit; 10 * 210 * .9985 = 2096.85 credit.
    assert out['cash_cents']==10_009_385
    assert out['paths']['one']['synthetic_pnl_cents']==9385
    assert out['paths']['one']['terminal_at']=='2024-05-28T13:30:00+00:00'
    assert out['paths']['one']['target'] is None
    assert sim.ledger.positions=={} and sim.ledger.slots()==[]


def test_entries_respect_exit_and_settlement_slot_then_reenter():
    t=tape()
    t['proposals'] += [dict(t['proposals'][0],id='blocked',signal_at='2024-05-24T13:32:00Z'),
                       dict(t['proposals'][0],id='next',signal_at='2024-05-28T13:30:00Z',target=1)]
    t['quotes']['SPY'] += [quote('2024-05-24T13:32:00Z'),quote('2024-05-28T13:30:00Z')]
    # Bar before opening is unusable; next candidate is registered after prior settlement.
    sim=Scheduler(t);out=sim.run()
    assert out['paths']['blocked']['status']=='observed_unfilled'
    assert sim.ledger.proposals['blocked']['attempts'][0]['reason']=='slot_or_underlying_occupied'
    assert sim.ledger.horizons['one']=='2024-05-28T13:30:00+00:00'
    assert sim.ledger.proposals['next']['selected_contract']=='N'
    assert out['paths']['next']['status']=='open'


@pytest.mark.parametrize('cost,expected',[(1,10009385),(2,10008770),(3,10008155)])
def test_cost_profiles_cash_and_position_size(cost,expected):
    policy=dict(BASELINE,cost_multiplier=cost)
    sim=Scheduler(tape(),policy);out=sim.run()
    assert out['cash_cents']==expected
    assert all(e['quantity']==10 for e in sim.ledger.events if e['kind']=='fill')


@pytest.mark.parametrize('fraction,quantity',[(.01,10),(.005,5),(.001,1)])
def test_shared_participation_stress(fraction,quantity):
    sim=Scheduler(tape(),dict(BASELINE,participation=fraction));sim.run()
    assert all(e['quantity']==quantity for e in sim.ledger.events if e['kind']=='fill')


@pytest.mark.parametrize('lag',[1,5,30,60])
def test_exact_entry_availability_and_deadline(lag):
    sim=Scheduler(tape(),dict(BASELINE,lag_seconds=lag));sim.run()
    fills=[e for e in sim.ledger.events if e['kind']=='fill']
    expected='2024-05-24T13:32:00+00:00' if lag==60 else f'2024-05-24T13:31:{lag:02d}+00:00'
    assert fills[0]['at']==expected


def test_no_trade_vs_missing_coverage_and_no_rescue_after_deadline():
    t=tape();t['bars']['A']=[bar('2024-05-24T13:31:00Z')]
    a=Scheduler(t);out=a.run()
    assert out['paths']['one']['status']=='observed_unfilled'
    assert not any(e['kind']=='fill' for e in a.ledger.events)
    t['coverage']['A']=False
    assert Scheduler(t).run()['paths']['one']['status']=='input_unresolved'


def test_future_changes_do_not_change_prefix_and_restart_is_exact():
    t=tape();a=Scheduler(t);a.run(20)
    snap=json.loads(json.dumps(a.snapshot()))
    b=Scheduler.restore(t,snap)
    assert b.run()==a.run()
    assert b.snapshot()==a.snapshot()
    changed=deepcopy(t);changed['bars']['A'].append(bar('2024-05-24T13:50:00Z',500))
    c=Scheduler(changed);c.run(20)
    assert c.ledger.snapshot()==snap['ledger']
    with pytest.raises(ValueError,match='input identity'):Scheduler.restore(changed,snap)
    snap['cursor']+=1
    with pytest.raises(ValueError,match='clock'):Scheduler.restore(t,snap)


def test_complete_stress_grid_and_deterministic_removal():
    assert len(stress_profiles())==27
    t=tape()
    rows=[bar(f'2024-05-24T13:{m:02d}:00Z') for m in range(30,60)]
    kept=stressed_bars(t['base'],{'A':rows},stress_profiles()['remove_every_tenth'])['A']
    assert [x['t'] for x in rows if x['t'] not in {b['t'] for b in kept}]==[
        '2024-05-24T13:39:00Z','2024-05-24T13:49:00Z','2024-05-24T13:59:00Z']
    assert len(stressed_bars(t['base'],{'A':rows},stress_profiles()['remove_first_0'])['A'])==25
    assert len(stressed_bars(t['base'],{'A':rows},stress_profiles()['combined'])['A'])==0


def test_minimum_activity_no_older_fallback():
    t=tape();t['bars']['A'][0]['n']=1
    assert Scheduler(t,dict(BASELINE,min_count=2)).run()['paths']['one']['status']=='observed_unfilled'


def physical_tape():
    t=tape();t['end']='2024-05-30T13:30:02Z';t['strategy_exits']=[]
    t['bars']['A']=t['bars']['A'][:1]
    t['bars']['A'][0]['v']=300
    t['quotes']['SPY'] += [quote('2024-05-24T13:45:00Z',210),quote('2024-05-29T13:30:00Z',210),
                           quote('2024-05-29T13:30:01Z',210)]
    t['exercises']={'A':[dict(kind='official_exercise_reference',contract='A',price=210,
        reference_at='2024-05-24T14:00:00Z',available_at='2024-05-24T14:00:02Z')]}
    return t


def test_auto_physical_clocks_delayed_reference_and_final_cash_horizon():
    sim=Scheduler(physical_tape());out=sim.run()
    assert out['paths']['one']['status']=='settled'
    assert out['cash_cents']==10_230_460  # -600.90 -60000 +62905.50
    assert out['paths']['one']['terminal_at']=='2024-05-30T13:30:00+00:00'
    events=sim.ledger.events
    assert next(e['at'] for e in events if e['kind']=='exercise_reservation')=='2024-05-24T14:00:02+00:00'
    assert next(e['at'] for e in events if e['kind']=='stock_sale')=='2024-05-29T13:30:01+00:00'


def test_stock_cost_and_exercise_fee_stresses_apply_to_all_legs():
    a=Scheduler(physical_tape(),dict(BASELINE,cost_multiplier=3));a.run()
    stock=next(e for e in a.ledger.events if e['kind']=='stock_sale')
    assert stock['fee']==189 and stock['slippage']==94.5
    b=Scheduler(physical_tape(),dict(BASELINE,exercise_fee=5));b.run()
    assert b.ledger.deliveries[0]['exercise_fee_cents']==1500


def test_fixed_boundary_census_retains_unsettled_cash_no_targets():
    t=tape()
    # Shift bounded ordinary round trip to the actual last market date.
    raw=json.dumps(t).replace('2024-05-24','2026-10-02').replace('2024-05-28','2026-10-05').replace('2024-05-29','2026-10-06')
    t=json.loads(raw)
    t['start']='2026-10-02T13:30:00Z';t['end']='2026-10-03T04:00:00Z'
    for terms in t['lifecycle']['terms'].values():terms['ends_at']='2026-10-10T00:00:00Z'
    t['lifecycle']['calendar']['business_dates']=['2026-10-02','2026-10-05','2026-10-06']
    # Parent constructor checks all option settlement dates; use the shifted complete mapping.
    t['base']['settlements']={'2026-10-02':'2026-10-05T13:30:00Z'}
    sim=Scheduler(t);out=sim.run()
    assert out['fixed_end_reached']
    assert out['paths']['one']['status']=='right_censored_end'
    assert out['paths']['one']['target'] is None and out['paths']['one']['terminal_at'] is None
    assert sim.ledger.cash==9_799_700


def test_duplicate_identity_and_bad_policy_rejected():
    t=tape();t['proposals'].append(deepcopy(t['proposals'][0]))
    with pytest.raises(ValueError,match='Duplicate'):Scheduler(t)
    with pytest.raises(ValueError,match='declared'):Scheduler(tape(),dict(BASELINE,cost_multiplier=-1))


def roll_tape():
    t=tape();t['end']='2024-05-28T13:32:02Z';t['strategy_exits']=[]
    t['bars']['A']=[bar('2024-05-24T13:30:00Z',2,300),bar('2024-05-24T13:44:00Z',1.9,300)]
    t['bars']['N']=[bar('2024-05-28T13:30:00Z',2,1000)]
    t['quotes']['SPY'] += [quote('2024-05-24T13:45:00Z',199),quote('2024-05-28T13:30:00Z',199),
                           quote('2024-05-28T13:31:00Z',199)]
    return t


def test_roll_automatic_consecutive_windows_and_stressed_budget():
    sim=Scheduler(roll_tape());sim.run()
    choices=[e for e in sim.ledger.events if e['kind']=='roll_selection']
    assert [e['at'] for e in choices[:2]]==['2024-05-28T13:30:00+00:00','2024-05-28T13:31:00+00:00']
    assert sim.ledger.positions['N']['quantity']==2
    assert sim.ledger.cash==9_956_764
    expensive=Scheduler(roll_tape(),dict(BASELINE,cost_multiplier=3));expensive.run()
    assert expensive.ledger.positions['N']['quantity']==2
    fills=[e for e in expensive.ledger.events if e['kind']=='fill']
    assert fills[-1]['cash_cents']==40180
    assert fills[-1]['cash_cents']<=sum(r['cents'] for r in expensive.ledger.receivables if r['settled'])


def test_missing_candidate_terms_is_unresolved_not_no_contract():
    t=tape();del t['lifecycle']['terms']['A']
    sim=Scheduler(t);out=sim.run()
    assert out['paths']['one']['status']=='input_unresolved'
    assert sim.ledger.outcome()['status']=='input_unresolved'


def test_mixed_symbols_share_cash_and_deterministic_signal_order():
    t=tape()
    t['proposals'].append(dict(t['proposals'][0],id='two',symbol='QQQ'))
    t['quotes']['QQQ']=[quote('2024-05-24T13:31:00Z',symbol='QQQ')]
    t['bars']['B']=deepcopy(t['bars']['A'])
    t['strategy_exits'].append(dict(at='2024-05-24T13:32:01Z',proposal_id='two'))
    a=Scheduler(t);out=a.run()
    assert out['cash_cents']==10_018_770
    assert out['census']=={'settled':2}
    assert [e['proposal_id'] for e in a.ledger.events if e['kind']=='fill' and e['side']=='buy']==['two','one']
    t['proposals'].reverse()
    assert Scheduler(t).run()==out


def test_study_all_profiles_resume_audit_and_corruption(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('integration_study',Path(__file__).resolve().parents[1]/'scripts/pilot_etfe_integration.py')
    study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
    assert not study.run(tmp_path,20)['complete']
    checkpoint=tmp_path/'ordinary--baseline.checkpoint-20.json'
    before=checkpoint.read_bytes()
    checkpoint.with_suffix('.sha256.json').unlink()  # interrupted receipt publication
    assert study.run(tmp_path)['combinations']==162
    assert checkpoint.read_bytes()==before
    assert study.audit(tmp_path)['combinations']==162
    checkpoint.write_bytes(before+b' ')
    with pytest.raises(ValueError,match='corruption'):study.audit(tmp_path)
