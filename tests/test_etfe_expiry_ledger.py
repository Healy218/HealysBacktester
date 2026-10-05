from copy import deepcopy
import json

import pytest

from nn_meta.etfe.execution_ledger import OptionLedger
from nn_meta.etfe.expiry_ledger import ExpiryLedger, settlement_clock


def fixture():
    days = ['2024-05-23', '2024-05-24', '2024-05-28', '2024-05-29', '2024-05-30', '2024-05-31', '2024-06-03']
    contracts = {
        'A': dict(symbol='SPY', right='C', expiration_date='2024-05-24'),
        'B': dict(symbol='QQQ', right='C', expiration_date='2024-05-24'),
        'N': dict(symbol='SPY', right='C', expiration_date='2024-05-29')}
    for terms in contracts.values():
        terms.update(multiplier=100, known_at='2024-05-22T14:00:00Z', expiry_close=terms['expiration_date']+'T20:00:00Z')
    sessions = {day: [day+'T13:30:00Z', day+'T20:00:00Z'] for day in days}
    base = dict(evidence_kind='synthetic', contracts=contracts, sessions={c: deepcopy(sessions) for c in contracts},
                settlements={day: days[i+1]+'T13:30:00Z' for i, day in enumerate(days[:-1])})
    lifecycle = dict(evidence_kind='synthetic', calendar=dict(evidence_kind='synthetic', business_dates=days),
        selection_complete=True, exercise_fee=0,
        stock_sessions={symbol: deepcopy(sessions) for symbol in ('SPY','QQQ','VOO')},
        terms={c: dict(strike=200, shares_per_contract=100, strike_cash_per_contract=20000, cash_per_contract=0,
                       exercise_basis='standard_per_share', known_at='2024-05-22T14:00:00Z',
                       effective_at='2024-05-22T00:00:00Z', ends_at='2024-06-04T00:00:00Z') for c in contracts})
    return base, lifecycle


def bar(at='2024-05-24T13:30:00Z', price=2, volume=300):
    return dict(t=at, vw=price, v=volume, n=10)


def quote(at, symbol='SPY', bid=210, ask=210.2, size=100, id=None, units=1):
    return dict(t=at, available_at=at, symbol=symbol, bid=bid, ask=ask, bid_size=size,
                ask_size=size, feed='sip', id=id or at, size_to_shares=units)


def reference(contract='A', price=210, at='2024-05-24T20:00:00Z'):
    return dict(kind='official_exercise_reference', contract=contract, price=price, reference_at=at, available_at=at)


def prefix(base=None, contracts=('A',), volume=300):
    base = base or fixture()[0]
    ledger = OptionLedger(base)
    ledger.step('2024-05-24T13:31:01Z', bars={c: [bar(volume=volume)] for c in contracts},
        entries=[dict(id=c, contract=c, signal_at='2024-05-24T13:31:00Z', target=1, qualifies=True, variant='alpha') for c in contracts])
    return ledger.snapshot()


def funded_call():
    base, lifecycle = fixture()
    ledger = ExpiryLedger(prefix(base), lifecycle)
    ledger.advance('2024-05-24T19:45:00Z', quotes={'SPY': quote('2024-05-24T19:45:00Z')}, coverage={'A': True})
    ledger.advance('2024-05-24T20:00:00Z', exercises={'A': reference()})
    return ledger


def test_funded_call_reserves_delivers_partial_liquidation_and_settles():
    ledger = funded_call()
    assert ledger.cash == 9_939_910
    assert ledger.available_cash() == 3_939_910
    assert ledger.deliveries[0]['shares'] == 300
    assert ledger.deliveries[0]['due'].startswith('2024-05-29T09:30:00')
    assert ledger.slots() == ['A']
    ledger.advance('2024-05-29T13:30:00Z', quotes={'SPY': quote('2024-05-29T13:30:00Z')})
    assert ledger.cash == 3_939_910 and ledger.stocks['A']['shares'] == 300
    assert not [e for e in ledger.events if e['kind'] == 'stock_sale']
    q = quote('2024-05-29T13:30:01Z')
    ledger.advance('2024-05-29T13:30:01Z', quotes={'SPY': q})
    assert ledger.stocks['A']['shares'] == 200
    assert ledger.receivables[-1]['cents'] == 2_096_850
    ledger.advance('2024-05-29T13:30:02Z', quotes={'SPY': q})
    assert ledger.stocks['A']['shares'] == 200
    ledger.advance('2024-05-29T13:30:03Z', quotes={'SPY': quote('2024-05-29T13:30:03Z',bid=211,ask=211.2,size=2,units=100)})
    assert ledger.stocks['A']['shares'] == 0
    assert ledger.receivables[-1]['cents'] == 4_213_670
    assert ledger.slots() == ['A']  # stock-sale settlement still owns the slot
    ledger.advance('2024-05-30T13:30:00Z')
    assert ledger.cash == 10_250_430
    assert ledger.outcome()['status'] == 'settled'
    assert ledger.slots() == []


def test_unfunded_put_never_creates_short_stock_or_sale():
    base, lifecycle = fixture()
    base['contracts']['A']['right'] = 'P'
    ledger = ExpiryLedger(prefix(base), lifecycle)
    ledger.advance('2024-05-24T20:00:00Z', exercises={'A': reference(price=190)})
    assert ledger.outcome(at_boundary=True)['status'] == 'funding_unresolved'
    assert ledger.positions['A']['quantity'] == 3
    assert not ledger.deliveries and not ledger.stocks
    assert ledger.cash == 9_939_910


def test_competing_exercises_reserve_cash_deterministically():
    base, lifecycle = fixture()
    ledger = ExpiryLedger(prefix(base, ('A','B')), lifecycle)
    ledger.advance('2024-05-24T20:00:00Z', exercises={c: reference(c) for c in ('A','B')})
    # QQQ sorts before SPY; $60,000 reserve leaves insufficient funds for SPY.
    assert [d['contract'] for d in ledger.deliveries] == ['B']
    assert ledger.available_cash() == 3_879_820
    assert ledger.unresolved[0]['contract'] == 'A'
    assert ledger.outcome()['status'] == 'funding_unresolved'


@pytest.mark.parametrize('price,exercised', [(199,False),(200,False),(200.009,False),(200.01,True)])
def test_official_threshold_and_nonexercise_has_no_zero_sale(price, exercised):
    _, lifecycle = fixture()
    ledger = ExpiryLedger(prefix(), lifecycle)
    ledger.advance('2024-05-24T20:00:00Z', exercises={'A': reference(price=price)})
    assert bool(ledger.deliveries) == exercised
    assert len([e for e in ledger.events if e['kind']=='fill']) == 1
    assert ledger.expired[0]['reason'] == ('exercise' if exercised else 'nonexercise')


@pytest.mark.parametrize('kind', ['future','missing','terms','fractional'])
def test_missing_or_future_exercise_evidence_stays_unresolved(kind):
    _, lifecycle = fixture()
    ref = reference()
    if kind=='future':ref['available_at']='2024-05-24T20:00:01Z'
    if kind=='missing':ref=None
    if kind=='terms':del lifecycle['terms']['A']
    if kind=='fractional':lifecycle['terms']['A']['shares_per_contract']=100.5
    ledger = ExpiryLedger(prefix(), lifecycle)
    ledger.advance('2024-05-24T20:00:00Z', exercises={'A': ref})
    assert ledger.outcome(at_boundary=True)['status']=='input_unresolved'
    assert ledger.positions and not ledger.deliveries


def test_settlement_transition_holiday_override_and_missing_calendar():
    calendar=fixture()[1]['calendar']
    assert settlement_clock('2024-05-24',calendar).startswith('2024-05-29')
    assert settlement_clock('2024-05-24',calendar,option=True).startswith('2024-05-28')
    assert settlement_clock('2024-05-28',calendar).startswith('2024-05-29')
    calendar['equity_overrides']={'2024-05-24':'2024-05-30'}
    assert settlement_clock('2024-05-24',calendar).startswith('2024-05-30')
    assert settlement_clock('2024-06-03',calendar) is None
    assert settlement_clock('2024-05-27',calendar) is None


def otm_roll():
    base, lifecycle=fixture()
    ledger=ExpiryLedger(prefix(base),lifecycle)
    ledger.advance('2024-05-24T19:45:01Z', bars={'A':[bar('2024-05-24T19:44:00Z',1.9,300)]},
        quotes={'SPY':quote('2024-05-24T19:45:01Z',bid=199,ask=199.2)})
    return ledger


def test_otm_roll_waits_for_settlement_uses_only_old_net_proceeds():
    ledger=otm_roll()
    assert not ledger.positions and ledger.rolls and ledger.cash==9_939_910
    assert ledger.receivables[0]['cents']==56_914
    ledger.advance('2024-05-24T19:46:00Z',roll_signals=['A'],quotes={'SPY':quote('2024-05-24T19:46:00Z',bid=199,ask=199.2)})
    assert ledger.rolls['A']['attempt'] is None
    ledger.advance('2024-05-28T13:31:00Z',roll_signals=['A'],quotes={'SPY':quote('2024-05-28T13:31:00Z',bid=199,ask=199.2)})
    assert ledger.rolls['A']['attempt']['contract']=='N'
    assert not ledger.positions
    ledger.advance('2024-05-28T13:31:01Z',bars={'N':[bar('2024-05-28T13:30:00Z',2,10000)]})
    # Old proceeds $569.14 fund two contracts at $200.30, not a fresh 10% allocation.
    assert ledger.positions['N']['quantity']==2
    assert ledger.positions['N']['entry_vwap']==2
    assert ledger.cash==9_956_764
    assert ledger.roll_counts['A']==1 and not ledger.rolls


def test_strategy_cancels_pending_roll_but_retains_slot_to_settlement():
    ledger=otm_roll()
    ledger.advance('2024-05-24T19:46:00Z',strategy_off=['A'])
    assert ledger.rolls['A']['cancelled'] and ledger.slots()==['A']
    ledger.advance('2024-05-28T13:30:00Z')
    assert not ledger.rolls and not ledger.slots()


def test_maximum_roll_count_and_missing_cutoff_quote():
    base,lifecycle=fixture()
    ledger=ExpiryLedger(prefix(base),lifecycle)
    ledger.roll_counts['A']=60  # synthetic boundary-state fixture
    ledger.advance('2024-05-24T19:45:01Z',bars={'A':[bar('2024-05-24T19:44:00Z',1.9)]})
    assert ledger.positions['A']['exit_intent'] is None and not ledger.rolls
    ledger.advance('2024-05-24T19:45:02Z',bars={'A':[bar('2024-05-24T19:44:00Z',1.9)]},
        quotes={'SPY':quote('2024-05-24T19:45:02Z',bid=199,ask=199.2)})
    assert not ledger.positions and not ledger.rolls


@pytest.mark.parametrize('change',[{'ask':209},{'bid_size':0},{'feed':'iex'}, {'t':'2024-05-24T19:44:00Z'}, {'available_at':'2024-05-24T19:45:02Z'}])
def test_invalid_stock_quote_cannot_classify_or_trade(change):
    _,lifecycle=fixture()
    ledger=ExpiryLedger(prefix(),lifecycle)
    q=quote('2024-05-24T19:45:01Z');q.update(change)
    ledger.advance('2024-05-24T19:45:01Z',quotes={'SPY':q},coverage={'A':True})
    assert ledger.positions['A']['exit_intent'] is None


def test_missing_liquidation_and_boundary_unsettled_differ():
    ledger=funded_call()
    assert ledger.outcome(at_boundary=True)['status']=='right_censored_end'
    ledger.advance('2024-05-29T13:30:01Z')
    assert ledger.outcome(at_boundary=True)['status']=='input_unresolved'
    assert ledger.stocks['A']['shares']==300
    with pytest.raises(ValueError):ledger.advance('2026-10-03T04:00:00Z')


def test_source_bound_resume_prefix_identity_and_atomicity():
    ledger=funded_call()
    restored=ExpiryLedger.restore(json.loads(json.dumps(ledger.snapshot())))
    for obj in (ledger,restored):
        obj.advance('2024-05-29T13:30:01Z',quotes={'SPY':quote('2024-05-29T13:30:01Z')})
    assert ledger.snapshot()==restored.snapshot()
    snap=ledger.snapshot();snap['state']['source']='wrong'
    with pytest.raises(ValueError):ExpiryLedger.restore(snap)
    before=ledger.snapshot()
    with pytest.raises(ValueError):ledger.advance('2024-05-28T13:30:00Z')
    assert ledger.snapshot()==before


def test_adjusted_deliverable_and_explicit_exercise_basis():
    _, lifecycle=fixture()
    lifecycle['terms']['A'].update(shares_per_contract=50,cash_per_contract=20,
        strike_cash_per_contract=10000,exercise_basis='official_intrinsic_per_share')
    ledger=ExpiryLedger(prefix(),lifecycle)
    ref=reference();ref['intrinsic_per_share']=10
    ledger.advance('2024-05-24T20:00:00Z',exercises={'A':ref})
    assert ledger.deliveries[0]['shares']==150
    assert ledger.deliveries[0]['debit_cents']==3_000_000
    assert ledger.deliveries[0]['credit_cents']==6000


def test_expiry_itm_exit_and_partial_residual_exercises_only_remaining():
    _, lifecycle=fixture()
    ledger=ExpiryLedger(prefix(),lifecycle)
    ledger.advance('2024-05-24T19:45:01Z',bars={'A':[bar('2024-05-24T19:44:00Z',3,100)]},
        quotes={'SPY':quote('2024-05-24T19:45:01Z')})
    assert ledger.positions['A']['quantity']==2
    assert ledger.positions['A']['exit_intent']=='expiry_itm'
    ledger.advance('2024-05-24T20:00:00Z',exercises={'A':reference()})
    assert ledger.deliveries[0]['shares']==200
    assert ledger.deliveries[0]['debit_cents']==4_000_000
    assert ledger.receivables[0]['cents']==29955


def test_exercise_fee_is_reserved_and_never_negative():
    _, lifecycle=fixture()
    lifecycle['exercise_fee']=5
    ledger=ExpiryLedger(prefix(),lifecycle)
    ledger.advance('2024-05-24T20:00:00Z',exercises={'A':reference()})
    assert ledger.deliveries[0]['debit_cents']==6_001_500
    assert ledger.deliveries[0]['exercise_fee_cents']==1500
    lifecycle['exercise_fee']=-1
    with pytest.raises(ValueError):ExpiryLedger(prefix(),lifecycle)


def test_roll_six_dte_rejected_and_new_entry_stop_denominator():
    ledger=otm_roll()
    # Only the future contract changes in a separately constructed fixture.
    base,lifecycle=fixture()
    base['contracts']['N'].update(expiration_date='2024-06-03',expiry_close='2024-06-03T20:00:00Z')
    ledger=ExpiryLedger(prefix(base),lifecycle)
    ledger.advance('2024-05-24T19:45:01Z',bars={'A':[bar('2024-05-24T19:44:00Z',1.9)]},
        quotes={'SPY':quote('2024-05-24T19:45:01Z',bid=199,ask=199.2)})
    ledger.advance('2024-05-28T13:31:00Z',roll_signals=['A'],quotes={'SPY':quote('2024-05-28T13:31:00Z')})
    assert ledger.rolls['A']['attempt']['contract'] is None
    assert ledger.rolls['A']['attempts'][-1]['reason']=='no_eligible_contract'
    ledger=otm_roll()
    ledger.advance('2024-05-28T13:31:00Z',roll_signals=['A'],quotes={'SPY':quote('2024-05-28T13:31:00Z')})
    ledger.advance('2024-05-28T13:31:01Z',bars={'N':[bar('2024-05-28T13:30:00Z',1)]})
    assert ledger.positions['N']['entry_vwap']==1
    ledger.advance('2024-05-28T13:32:01Z',bars={'N':[bar('2024-05-28T13:31:00Z',1.1)]})
    assert ledger.positions['N']['exit_intent'] is None


def test_missing_classification_not_mislabeled_boundary_and_retry():
    _,lifecycle=fixture()
    ledger=ExpiryLedger(prefix(),lifecycle)
    ledger.advance('2024-05-24T19:45:01Z',bars={'A':[bar('2024-05-24T19:44:00Z',1.9)]},coverage={'SPY':True})
    assert ledger.outcome(at_boundary=True)['status']=='input_unresolved'
    ledger.advance('2024-05-24T19:45:02Z',bars={'A':[bar('2024-05-24T19:44:00Z',1.9)]},
        quotes={'SPY':quote('2024-05-24T19:45:02Z')})
    assert not ledger.input_waits


def test_roll_reservation_blocks_competing_exercise_without_double_spend():
    base,lifecycle=fixture()
    # Expiry of B is after A sale settles, so its exercise must respect A's roll reserve.
    base['contracts']['B'].update(expiration_date='2024-05-28',expiry_close='2024-05-28T20:00:00Z')
    lifecycle['terms']['B'].update(strike=330, strike_cash_per_contract=33000)
    ledger=ExpiryLedger(prefix(base,('A','B')),lifecycle)
    ledger.advance('2024-05-24T19:45:01Z',bars={'A':[bar('2024-05-24T19:44:00Z',1.9)]},
        quotes={'SPY':quote('2024-05-24T19:45:01Z',bid=199,ask=199.2)},coverage={'B':True})
    ledger.advance('2024-05-28T20:00:00Z',exercises={'B':reference('B',400,'2024-05-28T20:00:00Z')})
    assert ledger.outcome()['status']=='funding_unresolved'
    assert ledger.roll_budget('A')==56914
    assert ledger.available_cash() < 9_900_000 <= ledger.cash


def test_prefix_unresolved_proposal_is_not_relabelled():
    base,lifecycle=fixture()
    ledger=OptionLedger(base)
    p=dict(id='missing',contract='A',signal_at='2024-05-24T13:31:00Z',target=1,qualifies=True,variant='alpha')
    ledger.step('2024-05-24T13:32:00Z',entries=[p])
    ledger.finish_entry('missing',window_coverage_complete=False)
    with pytest.raises(ValueError,match='Unresolved prefix'):
        ExpiryLedger(ledger.snapshot(),lifecycle)


def test_expiry_uses_dated_early_close_and_never_trades_after_it():
    base,lifecycle=fixture()
    base['contracts']['A']['expiry_close']='2024-05-24T17:00:00Z'
    base['sessions']['A']['2024-05-24'][1]='2024-05-24T17:00:00Z'
    lifecycle['stock_sessions']['SPY']['2024-05-24'][1]='2024-05-24T17:00:00Z'
    ledger=ExpiryLedger(prefix(base),lifecycle)
    ledger.advance('2024-05-24T16:45:01Z',quotes={'SPY':quote('2024-05-24T16:45:01Z')},coverage={'A':True})
    assert ledger.positions['A']['exit_intent']=='expiry_itm'
    ledger.advance('2024-05-24T17:00:00Z',bars={'A':[bar('2024-05-24T16:58:00Z',3)]},
        exercises={'A':reference(at='2024-05-24T17:00:00Z')})
    assert len([e for e in ledger.events if e['kind']=='fill'])==1
    assert ledger.deliveries[0]['quantity']==3


def test_expiry_study_resume_independent_audit_and_tamper(tmp_path):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('expiry_study',Path(__file__).resolve().parents[1]/'scripts/pilot_etfe_expiry.py')
    study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
    assert not study.run(tmp_path,2)['complete']
    before=(tmp_path/'funded-call-2.json').read_bytes()
    assert study.run(tmp_path)['complete']
    assert (tmp_path/'funded-call-2.json').read_bytes()==before
    assert study.audit(tmp_path)['prefixes']==13
    (tmp_path/'funded-call-2.json').write_bytes(before+b' ')
    with pytest.raises(ValueError,match='corruption'):study.run(tmp_path)
