"""Changed integration behavior, using the established ledger test fixtures."""
from types import SimpleNamespace
import pytest

from tests import test_v7_portfolio as option_cases
from tests import test_v7_physical as physical_cases
from nn_meta.v7.execution import CaptureUnavailable, QuotePolicy
from nn_meta.v7.integrated_portfolio import portfolio_replay
from nn_meta.v7.integrated_inputs import candidates_from_discovery, PhysicalInputs, BoundInputs
from nn_meta.v7.physical import PhysicalPolicy


@pytest.mark.parametrize('name', [
    'test_shared_slots_cross_timeframe_symbol_lock_and_costed_cash',
    'test_pending_fill_reserves_cash_and_slot_without_using_future_cash',
    'test_stale_held_equity_blocks_new_entry_but_observed_exit_still_executes',
    'test_incomplete_future_outcome_does_not_filter_entry_or_release_slot',
    'test_future_score_is_rejected',
    'test_roll_reuses_only_its_own_proceeds_with_other_cash_reserved',
    'test_exchange_dot_spelling_preserves_occ_root_identity',
])
def test_shared_allocator_behavior_preserved(name, monkeypatch):
    monkeypatch.setattr(option_cases, 'portfolio_replay', portfolio_replay)
    getattr(option_cases, name)()


def gap_candidate(key='a', symbol='SPY', *, decision=option_cases.T, score=1):
    p = option_cases.candidate(key, symbol, decision=decision, complete=False, score=score)
    p['path']['capture_complete'] = False
    p.update(pending_at_ns=decision+120*option_cases.SEC,
             pending_requests=[dict(kind='quotes', contract=p['path']['fills'][0]['contract'],
                                    start_ns=decision+90*option_cases.SEC,
                                    end_ns=decision+120*option_cases.SEC+1)])
    return p


def test_missing_admitted_path_stops_before_later_candidates_or_expiry():
    t, s = option_cases.T, option_cases.SEC
    a = gap_candidate()
    b = option_cases.candidate('b', 'QQQ', decision=t+180*s)
    r = portfolio_replay([a,b], [t,t+60*s,t+120*s,t+180*s,t+400*s], option_cases.Archive())
    assert r['stopped_at_ns'] == t+120*s and r['pending'] == a['pending_requests']
    assert r['cash'] == 90000 and set(r['open_positions']) == {'a'}
    assert len(r['fills']) == 1 and len(r['decisions']) == 1 and not r['complete']


def test_rejected_path_gap_does_not_block_admitted_path():
    t, s = option_cases.T, option_cases.SEC
    closed = option_cases.candidate('a', 'SPY', score=2)
    rejected = gap_candidate('b', 'QQQ', score=1)
    r = portfolio_replay([closed,rejected], [t,t+60*s,t+120*s,t+180*s], option_cases.Archive(), slots=1)
    assert r['complete'] and not r['pending']
    assert r['decisions'][1]['status'] == 'slots_full'


def test_missing_entry_retains_reservation_until_exact_gap():
    t,s=option_cases.T,option_cases.SEC
    p=gap_candidate();p['path']['fills']=[];p['pending_at_ns']=t
    r=portfolio_replay([p],[t,t+120*s],option_cases.Archive())
    assert r['stopped_at_ns']==t and r['reserved_cash']==10000
    assert r['active_proposals'] and not r['fills']


def test_missing_shared_equity_stops_before_known_later_exit():
    t,s=option_cases.T,option_cases.SEC
    class Missing(option_cases.Archive):
        pending=[dict(kind='quotes',purpose='shared_portfolio_mark')]
        def mark(self,contract,clock):
            if clock==t+60*s:raise CaptureUnavailable('missing')
            return super().mark(contract,clock)
    r=portfolio_replay([option_cases.candidate('a','SPY')],[t,t+60*s,t+180*s],Missing())
    assert len(r['fills'])==1 and r['cash']==90000 and r['stopped_at_ns']==t+60*s
    assert r['pending']==Missing.pending and not r['capture_complete']


def physical_context():
    class Stocks:
        pending=[]
        def mark(self,symbol,clock):
            return dict(bid=110.,sip_timestamp=clock,security_id='SPY-id',capture_identity='test-stock')
        def first_fill(self,symbol,clock,**kwargs):
            return physical_cases.stock_fill(symbol,clock)
    return SimpleNamespace(settlement_calendar=physical_cases.calendar(),policy=PhysicalPolicy(),
        stock_archive=Stocks(),expiry_check_clock=lambda contract:physical_cases.ns('2024-05-24'),
        expiry_evidence=physical_cases.evidence,pending=[])


def physical_candidate():
    decision=physical_cases.ns('2024-05-23','14:59')
    p=option_cases.candidate('a','SPY',decision=decision,complete=False)
    p['security_id']='SPY-id'
    p['path']['fills'][0]['contract']='SPY240524C00100000'
    return p


def test_integrated_physical_call_settles_liquidates_and_keeps_cash_locked():
    p=physical_candidate();ctx=physical_context();ns=physical_cases.ns
    r=portfolio_replay([p],[p['decision_ns'],ns('2024-05-24'),ns('2024-05-30','13:30'),
        ns('2024-06-03','13:30')],option_cases.Archive(),physical=ctx,fraction=.001,
        policy=QuotePolicy(fee=0,slippage=0))
    assert r['complete'] and not r['physical_commitments'] and not r['open_positions']
    assert r['physical_completed_at']['a']==ns('2024-06-03','13:30')
    assert r['cash']==pytest.approx(99900-10000+11000*.9985)
    assert [e.get('kind') for e in r['fills']]==[None,'exercise','delivery_commitment',
        'settlement','stock_delivery','stock_sale','settlement']


def test_unfunded_exercise_stops_without_later_capital_reallocation():
    p=physical_candidate();ns=physical_cases.ns
    r=portfolio_replay([p],[p['decision_ns'],ns('2024-05-24'),ns('2024-06-03','13:30')],
        option_cases.Archive(),physical=physical_context(),fraction=.1)
    assert not r['complete'] and r['decisions'][-1]['status']=='unresolved_exercise_funding'
    assert r['stopped_at_ns']==ns('2024-05-24','21:00') and r['open_positions']
    assert not r['physical_commitments']


def test_missing_official_evidence_requested_at_expiry_and_preserves_option():
    p=physical_candidate();ctx=physical_context();ns=physical_cases.ns
    ctx.pending=[dict(kind='exercise_reference')]
    def missing(contract):raise CaptureUnavailable('official evidence missing')
    ctx.expiry_evidence=missing
    r=portfolio_replay([p],[p['decision_ns'],ns('2024-05-24'),ns('2024-06-03','13:30')],
        option_cases.Archive(),physical=ctx,fraction=.001)
    assert r['stopped_at_ns']==ns('2024-05-24') and r['pending']==ctx.pending
    assert len(r['fills'])==1 and r['open_positions']['a']['phase']=='option'


def test_closed_option_path_needs_no_expiry_evidence():
    p=physical_candidate();first=p['path']['fills'][0];ctx=physical_context()
    end=first['sip_timestamp']+60*option_cases.SEC
    p['path'].update(label_complete=True,label_end_ns=end)
    p['path']['fills'].append(dict(first,side='sell',decision_ns=end,sip_timestamp=end))
    def unexpected(contract):raise AssertionError('Closed position requested expiry input')
    ctx.expiry_check_clock=unexpected
    r=portfolio_replay([p],[p['decision_ns'],end],option_cases.Archive(),physical=ctx)
    assert r['complete']


def test_missing_input_after_fill_is_not_backdated():
    p=gap_candidate();p['pending_at_ns']=p['path']['fills'][0]['sip_timestamp']
    with pytest.raises(ValueError,match='unresolved dependency'):
        portfolio_replay([p],[p['decision_ns'],p['pending_at_ns']],option_cases.Archive())


def test_source_path_adapter_keeps_incomplete_candidate_and_exact_clock():
    p=gap_candidate();at=p['pending_at_ns']
    p['path'].update(marks=[dict(clock_ns=at,status='uncaptured')],attempts=[],
                     open_positions={'position':{}},label_end_ns=None)
    case=dict(source_proposal={k:p[k] for k in ('proposal_id','symbol','decision_ns')},
              security_id='SPY-id',replay=p['path'],pending=p['pending_requests'])
    candidates=candidates_from_discovery(dict(cases=[case]))
    assert len(candidates)==1 and candidates[0]['pending_at_ns']==at
    assert candidates[0]['pending_requests']==p['pending_requests']
    assert candidates[0]['score']==0 and candidates[0]['path'] is p['path']


def test_physical_adapter_missing_reference_is_explicit_without_creating_files(tmp_path):
    context=PhysicalInputs(settlement_calendar=physical_cases.calendar(),stock_archive=None,
        hours=SimpleNamespace(cutoff=lambda contract:100),references=None,
        expiry_root=tmp_path/'absent',bindings=BoundInputs())
    contract='SPY240524C00100000'
    assert context.expiry_check_clock(contract)==100+15*60_000_000_000
    with pytest.raises(CaptureUnavailable,match='official expiration'):
        context.expiry_evidence(contract)
    assert context.pending[0]['contract']==contract
    assert context.pending[0]['date']=='2024-05-24'
    assert not (tmp_path/'absent').exists()
