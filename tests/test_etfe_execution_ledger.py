"""Independent hand arithmetic and adversarial clock/capital checks."""
import json

import pytest

from nn_meta.etfe.execution_ledger import OptionLedger, cents


def fixture():
    return dict(evidence_kind='synthetic', contracts={
        'A': dict(symbol='SPY', right='C', multiplier=100, expiration_date='2024-01-19',
                  expiry_close='2024-01-19T21:00:00Z', known_at='2024-01-17T15:00:00Z'),
        'B': dict(symbol='QQQ', right='P', multiplier=100, expiration_date='2024-01-19',
                  expiry_close='2024-01-19T21:00:00Z', known_at='2024-01-17T15:00:00Z')},
        sessions={c: {f'2024-01-{d}': [f'2024-01-{d}T14:30:00Z', f'2024-01-{d}T21:00:00Z']
                      for d in ('18', '19')} for c in ('A', 'B')},
        settlements={'2024-01-18': '2024-01-19T14:30:00Z', '2024-01-19': '2024-01-22T14:30:00Z'})


def proposal(id='p', contract='A', **kw):
    return dict(id=id, contract=contract, signal_at='2024-01-18T14:31:00Z',
                variant='alpha', target=1, qualifies=True, **kw)


def bar(minute='30', price=2., volume=1000, **kw):
    return dict(t=f'2024-01-18T14:{minute}:00Z', vw=price, v=volume, n=10, **kw)


def enter(ledger=None, volume=1000):
    ledger = ledger or OptionLedger(fixture())
    ledger.step('2024-01-18T14:31:01Z', bars={'A': [bar(volume=volume)]},
                entries=[proposal()], coverage={'A': True})
    return ledger


def test_hand_cash_partial_stop_latched_recovery_settlement():
    ledger = enter()
    # 10 contracts at $200 + $0.20 fee + $0.10 slippage each.
    assert ledger.cash == 9_799_700
    assert ledger.positions['A']['quantity'] == 10
    ledger.step('2024-01-18T14:32:01Z', bars={'A': [bar('31', 1.7, 400)]}, coverage={'A': True})
    assert ledger.positions['A']['quantity'] == 6
    assert ledger.positions['A']['exit_intent'] == 'premium_stop'
    assert ledger.receivables[0]['cents'] == 67_898  # 680 - .68 - .34
    # Same bar capacity is exhausted, even though the intent remains live.
    ledger.step('2024-01-18T14:32:02Z', bars={'A': [bar('31', 1.7, 400)]}, coverage={'A': True})
    assert ledger.positions['A']['quantity'] == 6
    # Recovered premium does not cancel the latched stop.
    ledger.step('2024-01-18T14:33:01Z', bars={'A': [bar('32', 2.1, 600)]}, coverage={'A': True})
    assert not ledger.positions
    assert ledger.receivables[1]['cents'] == 125_811  # 1260 - 1.26 - .63
    assert ledger.cash == 9_799_700
    assert ledger.outcome()['status'] == 'open'
    ledger.step('2024-01-19T14:30:00Z')
    assert ledger.cash == 9_993_409  # $65.91 loss including both sides' costs
    assert ledger.outcome()['status'] == 'settled'


def test_budget_is_ten_percent_whole_contracts():
    ledger = enter(volume=100_000)
    assert ledger.positions['A']['quantity'] == 49
    assert ledger.cash == 9_018_530  # 49 * $200.30


def test_no_topup_and_shared_buy_sell_capacity():
    ledger = enter()
    ledger.step('2024-01-18T14:31:02Z', bars={'A': [bar()]}, entries=[proposal()], exits=['A'])
    assert ledger.positions['A']['quantity'] == 10
    assert len([e for e in ledger.events if e['kind'] == 'fill']) == 1
    assert ledger.used['A|2024-01-18T14:30:00+00:00'] == 10


def test_sequential_allocation_and_deterministic_ties():
    outputs = []
    for ps in ([proposal('a'), proposal('b', 'B')], [proposal('b', 'B'), proposal('a')]):
        ledger = OptionLedger(fixture())
        ledger.step('2024-01-18T14:31:01Z', entries=ps,
                    bars={c: [bar(price=10, volume=100_000)] for c in ('A', 'B')})
        outputs.append(ledger.snapshot())
        assert [e['contract'] for e in ledger.events if e['kind'] == 'fill'] == ['B', 'A']
        assert all(p['quantity'] == 9 for p in ledger.positions.values())
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize('complete,status', [(True, 'observed_unfilled'), (False, 'input_unresolved')])
def test_deadline_no_trade_and_missing_coverage(complete, status):
    ledger = OptionLedger(fixture())
    ledger.step('2024-01-18T14:31:01Z', entries=[proposal()], coverage={'A': complete})
    with pytest.raises(ValueError, match='not finished'):
        ledger.finish_entry('p', window_coverage_complete=complete)
    # The 14:31 bar isn't available until AFTER the 14:32 deadline.
    ledger.step('2024-01-18T14:32:00Z', entries=[proposal()], bars={'A': [bar('31')]}, coverage={'A': complete})
    assert ledger.finish_entry('p', window_coverage_complete=complete) == status
    ledger.step('2024-01-18T14:32:01Z', entries=[proposal()], bars={'A': [bar('31')]})
    assert not ledger.positions


@pytest.mark.parametrize('bad', [dict(vw=0), dict(v=-1), dict(n=0), dict(vw=float('nan'))])
def test_invalid_newer_bar_never_falls_back(bad):
    ledger = OptionLedger(fixture())
    newer = bar('31')
    newer.update(bad)
    ledger.step('2024-01-18T14:32:01Z', bars={'A': [bar(), newer]}, entries=[dict(proposal(), signal_at='2024-01-18T14:32:00Z')])
    assert ledger.proposals['p']['attempts'][0]['reason'] == 'newest_bar_invalid'
    assert not ledger.positions


def test_missing_mark_blocks_new_risk_then_recovers_but_failure_retained():
    ledger = enter()
    ledger.step('2024-01-18T14:32:01Z', bars={'B': [bar('31')]},
                entries=[dict(proposal('b', 'B'), signal_at='2024-01-18T14:32:00Z')])
    assert ledger.last_equity is None
    assert 'B' not in ledger.positions
    assert ledger.positions['A']['last_mark_audit_only'] == 2
    ledger.step('2024-01-18T14:33:01Z', bars={'A': [bar('32')]}, coverage={'A': True})
    assert ledger.last_equity == 99_997
    assert ledger.outcome(at_boundary=True)['status'] == 'input_unresolved'


def test_settlement_before_entries_and_no_early_reuse():
    ledger = enter()
    ledger.step('2024-01-18T14:32:01Z', bars={'A': [bar('31', 2, 1000)]}, exits=['A'])
    assert ledger.cash == 9_799_700
    ledger.step('2024-01-19T14:31:01Z', entries=[dict(proposal('next', 'B'), signal_at='2024-01-19T14:31:00Z')],
                bars={'B': [dict(bar(), t='2024-01-19T14:30:00Z')]})
    events = [e for e in ledger.events if e['at'] == ledger.clock]
    assert events[0]['kind'] == 'settlement'
    assert ledger.cash == 9_799_100


@pytest.mark.parametrize('expiry,target,accepted', [('2024-01-18',0,True), ('2024-01-23',5,True), ('2024-01-24',5,False)])
def test_actual_zero_through_five_dte(expiry, target, accepted):
    f = fixture()
    f['contracts']['A'].update(expiration_date=expiry, expiry_close=expiry+'T21:00:00Z')
    ledger = OptionLedger(f)
    ledger.step('2024-01-18T14:31:01Z', entries=[dict(proposal(), target=target)], bars={'A': [bar()]})
    assert bool(ledger.positions) == accepted


def test_early_close_cutoff_and_no_after_close_fill():
    f = fixture()
    f['contracts']['A'].update(expiration_date='2024-01-18', expiry_close='2024-01-18T18:00:00Z')
    f['sessions']['A']['2024-01-18'][1] = '2024-01-18T18:00:00Z'
    ledger = OptionLedger(f)
    ledger.step('2024-01-18T17:45:00Z', entries=[dict(proposal(), signal_at='2024-01-18T17:44:59Z')],
                bars={'A': [dict(bar(), t='2024-01-18T17:44:00Z')]})
    assert ledger.proposals['p']['attempts'][0]['reason'] == 'expiry_exit_cutoff_reached'
    ledger = enter(OptionLedger(f))
    ledger.step('2024-01-18T18:00:00Z', exits=['A'], bars={'A': [dict(bar(), t='2024-01-18T17:58:00Z')]}, coverage={'A': True})
    assert ledger.positions['A']['quantity'] == 10
    assert ledger.outcome(at_boundary=True)['status'] == 'input_unresolved'


def test_missing_settlement_and_boundary_are_distinct():
    f = fixture()
    f['settlements'] = {}
    ledger = enter(OptionLedger(f))
    ledger.step('2024-01-18T14:32:01Z', exits=['A'], bars={'A': [bar('31')]})
    assert ledger.outcome(at_boundary=True)['status'] == 'input_unresolved'
    clean = enter()
    assert clean.outcome(at_boundary=True)['status'] == 'right_censored_end'
    with pytest.raises(ValueError):
        clean.step('2026-10-03T04:00:00Z')


def test_resume_matches_and_rejects_changed_source():
    ledger = enter()
    snapshot = json.loads(json.dumps(ledger.snapshot()))
    restored = OptionLedger.restore(snapshot)
    for obj in (ledger, restored):
        obj.step('2024-01-18T14:32:01Z', bars={'A': [bar('31', 1.7, 400)]})
    assert ledger.snapshot() == restored.snapshot()
    snapshot['state']['source'] = 'bad'
    with pytest.raises(ValueError, match='source'):
        OptionLedger.restore(snapshot)


def test_proposal_identity_prior_date_and_duplicate_preflight():
    ledger = enter()
    before = ledger.snapshot()
    with pytest.raises(ValueError, match='changed'):
        ledger.step('2024-01-18T14:31:02Z', entries=[dict(proposal(), target=5)])
    assert ledger.snapshot() == before
    with pytest.raises(ValueError, match='Duplicate'):
        ledger.step('2024-01-18T14:31:02Z', entries=[proposal('x'), proposal('x')])
    f = fixture()
    f['contracts']['A']['known_at'] = '2024-01-18T14:00:00Z'
    assert not enter(OptionLedger(f)).positions


def test_real_data_rejected_and_cash_half_even():
    with pytest.raises(ValueError, match='Real execution'):
        OptionLedger(dict(fixture(), evidence_kind='alpaca'))
    assert cents(1.005) == 100
    assert cents(1.015) == 102


def test_revision_conflicts_and_late_publication():
    ledger = enter()
    ledger.step('2024-01-18T14:31:02Z', bars={'A': [bar(price=1.5)]}, coverage={'A': True})
    assert ledger.positions['A']['mark'] is None
    ledger = OptionLedger(fixture())
    ledger.step('2024-01-18T14:31:01Z', entries=[proposal()], bars={'A': [bar(available_at='2024-01-18T14:32:01Z')]})
    assert not ledger.positions


def test_low_participation_immutable_retry_and_no_second_underlying():
    ledger = enter(volume=99)
    assert not ledger.positions
    assert ledger.proposals['p']['attempts'][0]['reason'] == 'size_ineligible'
    ledger = enter()
    ledger.step('2024-01-18T14:31:02Z', entries=[proposal('other')], bars={'A': [bar()]})
    assert ledger.proposals['other']['attempts'][0]['reason'] == 'slot_or_underlying_occupied'


def test_malformed_frame_rolls_back_and_tampered_quantity_rejected():
    ledger = enter()
    previous = ledger.snapshot()
    with pytest.raises(ValueError):
        ledger.step('2024-01-18T14:32:01Z', bars={'A': [dict(bar(), t='naive')]})
    assert ledger.snapshot() == previous
    previous['state']['positions']['A']['quantity'] = 11
    with pytest.raises(AssertionError):
        OptionLedger.restore(previous)


def test_synthetic_study_resume_audit_and_corruption(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('execution_study', Path(__file__).resolve().parents[1] / 'scripts/pilot_etfe_execution.py')
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    assert not study.run(tmp_path, 2)['complete']
    before = (tmp_path / 'checkpoint-2.json').read_bytes()
    assert study.run(tmp_path)['complete']
    assert (tmp_path / 'checkpoint-2.json').read_bytes() == before
    assert study.audit(tmp_path)['pnl_cents'] == -6591
    (tmp_path / 'checkpoint-2.json').write_bytes(before + b' ')
    with pytest.raises(ValueError, match='corruption'):
        study.run(tmp_path)
