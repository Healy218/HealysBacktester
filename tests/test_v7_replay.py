import pandas as pd
import pytest

from nn_meta.v7.replay import replay
from nn_meta.v7.execution import CaptureUnavailable, QuoteUnavailable
from options.data.provider import parse_occ_symbol


OLD = 'SPY220309C00420000'
NEW = 'SPY220311C00420000'
ENTRY = pd.Timestamp('2022-03-07T14:31Z').value
ROLL = pd.Timestamp('2022-03-09T21:00Z').value
EXIT = pd.Timestamp('2022-03-10T15:00Z').value


class References:
    def standard(self, contract, day):
        root, expiry, right, strike = parse_occ_symbol(contract)
        return {'underlying': root, 'right': right, 'expiry': expiry, 'metadata_receipt_sha256': 'fixture'}


class Archive:
    def __init__(self, missing_exit=False, missing_roll=False, missing_capture=False, stale_marks=False):
        self.missing_exit, self.missing_roll = missing_exit, missing_roll
        self.missing_capture, self.stale_marks = missing_capture, stale_marks

    def first_fill(self, contract, clock, *, side, deadline_ns):
        if self.missing_capture and side == 'sell':
            raise CaptureUnavailable('fixture uncaptured exit window')
        if self.missing_exit and side == 'sell' or self.missing_roll and contract == NEW:
            return None
        prices = {(OLD, 'buy'): 1., (OLD, 'sell'): 1.2, (NEW, 'buy'): 2., (NEW, 'sell'): 2.2}
        return {'contract': contract, 'side': side, 'price': prices[contract, side],
                'decision_ns': clock, 'sip_timestamp': clock + 1_000_000_000}

    def mark(self, contract, clock):
        if self.stale_marks:
            raise QuoteUnavailable('fixture observed stale market')
        return {'bid': .99 if contract == OLD else 1.99, 'ask': 1.01 if contract == OLD else 2.01,
                'price': 1. if contract == OLD else 2., 'sip_timestamp': clock}


def run(archive, exit_at=EXIT):
    return replay({'proposal_id': 'test', 'symbol': 'SPY', 'right': 'C', 'decision_ns': ENTRY,
                   'exit_decision_ns': exit_at}, [ENTRY, ENTRY + 60_000_000_000, ROLL, EXIT], archive, References(),
                  select_contract=lambda t: OLD if t < ROLL else NEW,
                  expiry_cutoff=lambda c: ROLL if c == OLD else EXIT + 86_400_000_000_000,
                  session_close=lambda t: t + 900_000_000_000,
                  underlying_mark=lambda s,t: {'price':400., 'sip_timestamp':t})


def test_roll_reinvests_observed_proceeds_and_all_four_costed_fills_reconcile():
    result = run(Archive())
    expected = (1.2 * .9985 / 1.0015) * (2.2 * .9985 / (2 * 1.0015)) - 1
    assert result['label_complete'] and result['rolls'] == 1
    assert len(result['fills']) == 4
    assert result['net_return'] == pytest.approx(expected)
    assert result['label_end_ns'] == EXIT + 1_000_000_000


def test_pending_roll_keeps_label_horizon_until_actual_strategy_exit():
    result = run(Archive(missing_roll=True))
    assert result['label_complete'] and not result['open_positions']
    assert result['status'] == 'signal_exit_while_roll_unfilled'
    assert result['label_end_ns'] == EXIT > result['fills'][-1]['sip_timestamp']


def test_unfilled_expiry_and_uncaptured_exit_are_never_fabricated_closed_returns():
    result = run(Archive(missing_exit=True))
    assert not result['label_complete'] and result['open_positions']
    assert result['status'] == 'expiry_liquidation_unresolved' and result['net_return'] is None
    result = run(Archive(missing_capture=True))
    assert not result['capture_complete'] and not result['label_complete']
    assert result['open_positions']


def test_sparse_observed_marks_remain_visible_and_open_proposals_are_censored():
    result = run(Archive(stale_marks=True))
    assert result['label_complete'] and not result['mark_coverage_complete']
    assert all(row['status'] == 'unavailable' for row in result['marks'])
    result = run(Archive(), exit_at=None)
    assert not result['label_complete'] and result['open_positions'] and result['net_return'] is None


def test_option_stop_sells_at_trigger_midpoint_without_requesting_another_quote():
    stop = ENTRY+60_000_000_000
    recovery = stop+60_000_000_000
    class Falling(Archive):
        def mark(self, contract, clock):
            value = .875 if clock==stop else 1.
            return {'price':value,'sip_timestamp':clock-5_000_000_000}
        def first_fill(self, contract, clock, *, side, deadline_ns):
            if side=='sell':pytest.fail('Stop requested a second quote instead of its observed midpoint')
            return {'contract':contract,'side':side,'price':1.,'decision_ns':clock,
                    'sip_timestamp':clock+1_000_000_000}
    result = replay({'proposal_id':'stop','symbol':'SPY','right':'C','decision_ns':ENTRY,
        'exit_decision_ns':None},[ENTRY,stop,recovery],Falling(),References(),
        select_contract=lambda t:OLD,expiry_cutoff=lambda c:ROLL,session_close=lambda t:t+900_000_000_000)
    assert result['label_complete'] and result['status']=='option_midpoint_stop'
    assert result['risk_exit']['clock_ns']==stop
    assert result['fills'][-1]['decision_ns']==stop
    assert result['fills'][-1]['sip_timestamp']==stop-5_000_000_000
    assert result['fills'][-1]['execution_ns']==result['label_end_ns']==stop
    assert result['risk_exit']['entry_midpoint']==1.
    assert result['net_return']==pytest.approx(.875*.9985/1.0015-1)
    from nn_meta.v7.portfolio import portfolio_replay
    shared=portfolio_replay([dict(proposal_id='stop',symbol='SPY',decision_ns=ENTRY,score=.5,
        score_available_ns=ENTRY,path=result)],[ENTRY,stop],Falling())
    assert shared['complete'] and not shared['open_positions']


def test_itm_expiry_closes_instead_of_opening_replacement():
    result = replay({'proposal_id':'expiry','symbol':'SPY','right':'C','decision_ns':ENTRY,
        'exit_decision_ns':EXIT},[ENTRY,ROLL,EXIT],Archive(),References(),
        select_contract=lambda t:OLD if t<ROLL else NEW,expiry_cutoff=lambda c:ROLL,
        session_close=lambda t:t+900_000_000_000,
        underlying_mark=lambda s,t:{'price':421.,'sip_timestamp':t})
    assert result['label_complete'] and result['status']=='itm_expiry_exit'
    assert result['rolls']==0 and len(result['fills'])==2
    assert result['label_end_ns']==ROLL


def test_expiry_without_underlying_capture_is_not_assumed_out_of_the_money():
    result = replay({'proposal_id':'expiry','symbol':'SPY','right':'C','decision_ns':ENTRY,
        'exit_decision_ns':EXIT},[ENTRY,ROLL,EXIT],Archive(),References(),
        select_contract=lambda t:OLD,expiry_cutoff=lambda c:ROLL,
        session_close=lambda t:t+900_000_000_000)
    assert not result['label_complete'] and not result['capture_complete']
    assert result['status']=='capture_incomplete' and len(result['fills'])==1


def test_stale_expiry_stock_quote_retries_without_assuming_otm_or_rolling():
    retry = ROLL+60_000_000_000
    result = replay({'proposal_id':'expiry','symbol':'SPY','right':'C','decision_ns':ENTRY,
        'exit_decision_ns':EXIT},[ENTRY,ROLL,retry],Archive(),References(),
        select_contract=lambda t:OLD if t<ROLL else pytest.fail('Must not roll unknown expiry'),
        expiry_cutoff=lambda c:ROLL,session_close=lambda t:t+900_000_000_000,
        underlying_mark=lambda s,t:{'price':421., 'sip_timestamp':t-(31_000_000_000 if t==ROLL else 0)})
    assert result['label_complete'] and result['status']=='itm_expiry_exit'
    assert result['label_end_ns']==retry and result['rolls']==0
    assert any(a['clock_ns']==ROLL and a['status']=='unavailable' for a in result['attempts'])
