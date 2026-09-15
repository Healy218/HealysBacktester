import pandas as pd
import pytest

from nn_meta.v7.portfolio import portfolio_replay
from nn_meta.v7.execution import QuoteUnavailable


T = pd.Timestamp('2022-03-07T15:00Z').value
SEC = 1_000_000_000


class Archive:
    def __init__(self, stale=()):
        self.stale = stale

    def mark(self, contract, clock):
        if clock in self.stale:
            raise QuoteUnavailable('Observed stale quote')
        return {'bid': 1., 'sip_timestamp': clock}


def candidate(key, symbol, *, decision=T, fill_delay=1, exit_delay=180, score=1., complete=True):
    contract = symbol + '220311C00420000'
    fills = [{'contract': contract, 'side': 'buy', 'price': 1., 'decision_ns': decision,
              'sip_timestamp': decision + fill_delay * SEC}]
    if complete:
        fills.append({'contract': contract, 'side': 'sell', 'price': 1.1,
                      'decision_ns': decision + (exit_delay-1)*SEC,
                      'sip_timestamp': decision + exit_delay*SEC})
    return {'proposal_id': key, 'symbol': symbol, 'decision_ns': decision,
            'score': score, 'score_available_ns': decision,
            'path': {'proposal_id': key, 'fills': fills, 'capture_complete': True,
                     'label_complete': complete, 'label_end_ns': decision + exit_delay*SEC if complete else None}}


def test_shared_slots_cross_timeframe_symbol_lock_and_costed_cash():
    candidates = [candidate('a', 'SPY', score=3), candidate('b', 'SPY', score=2),
                  candidate('c', 'QQQ', score=1), candidate('d', 'IWM', score=0)]
    result = portfolio_replay(candidates, [T, T+60*SEC, T+180*SEC], Archive(), slots=2)
    assert [r['status'] for r in result['decisions']] == ['reserved', 'symbol_occupied', 'reserved', 'slots_full']
    assert result['cash'] == pytest.approx(80000 + 20000 * 1.1 * .9985 / 1.0015)
    assert result['complete'] and len(result['fills']) == 4 and result['reserved_cash'] == 0


def test_pending_fill_reserves_cash_and_slot_without_using_future_cash():
    candidates = [candidate('a', 'SPY', fill_delay=50), candidate('b', 'QQQ', decision=T+10*SEC)]
    result = portfolio_replay(candidates, [T, T+10*SEC, T+200*SEC], Archive(), fraction=1.)
    assert result['decisions'][1]['status'] == 'no_cash'
    assert result['complete'] and len(result['fills']) == 2


def test_stale_held_equity_blocks_new_entry_but_observed_exit_still_executes():
    candidates = [candidate('a', 'SPY'), candidate('b', 'QQQ', decision=T+60*SEC)]
    result = portfolio_replay(candidates, [T, T+60*SEC, T+240*SEC], Archive(stale=[T+60*SEC]))
    assert result['decisions'][1]['status'] == 'equity_unavailable'
    assert result['complete'] and len(result['fills']) == 2 and not result['valuation_complete']


def test_incomplete_future_outcome_does_not_filter_entry_or_release_slot():
    candidates = [candidate('a', 'SPY', score=2, complete=False), candidate('b', 'QQQ', score=1)]
    result = portfolio_replay(candidates, [T, T+240*SEC], Archive(), slots=1)
    assert result['decisions'][0]['status'] == 'reserved'
    assert result['decisions'][1]['status'] == 'slots_full'
    assert not result['complete'] and 'a' in result['open_positions']


def test_future_score_is_rejected():
    p = candidate('a', 'SPY')
    p['score_available_ns'] += SEC
    with pytest.raises(ValueError, match='Causal'):
        portfolio_replay([p], [T, T+240*SEC], Archive())


def test_roll_reuses_only_its_own_proceeds_with_other_cash_reserved():
    p = candidate('a', 'SPY')
    old = p['path']['fills'][0]['contract']
    new = 'SPY220314C00420000'
    p['path']['fills'] = [p['path']['fills'][0],
        {'contract': old, 'side': 'sell', 'price': 1.2, 'decision_ns': T+59*SEC, 'sip_timestamp': T+60*SEC},
        {'contract': new, 'side': 'buy', 'price': 2., 'decision_ns': T+60*SEC, 'sip_timestamp': T+61*SEC, 'roll_of': 1},
        {'contract': new, 'side': 'sell', 'price': 2.2, 'decision_ns': T+179*SEC, 'sip_timestamp': T+180*SEC}]
    result = portfolio_replay([p], [T, T+60*SEC, T+180*SEC], Archive())
    expected = 90000 + 10000 * (1.2*.9985/1.0015) * (2.2*.9985/(2*1.0015))
    assert result['complete'] and result['cash'] == pytest.approx(expected)


def test_exchange_dot_spelling_preserves_occ_root_identity():
    p = candidate('a', 'BRKB')
    p['symbol'] = 'BRK.B'
    result = portfolio_replay([p], [T, T+180*SEC], Archive())
    assert result['complete'] and len(result['fills']) == 2
