from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.execution import QuotePolicy, QuoteUnavailable
from nn_meta.v7.physical import PhysicalLedger, PhysicalPolicy, SettlementCalendar
from nn_meta.v7.portfolio import portfolio_replay


def ns(day, hour='20:00'):
    return int(pd.Timestamp(day+'T'+hour+'Z').value)


def calendar():
    days = [d.date().isoformat() for d in pd.bdate_range('2024-05-20', '2024-06-10')
            if d.date().isoformat() != '2024-05-27']
    trading = SessionCalendar({'coverage_start': days[0], 'coverage_end': days[-1],
        'sessions': [dict(date=d, open='09:30', close='16:00') for d in days]})
    return SettlementCalendar(dict(schema='v7-settlement-calendar-v1', business_dates=days,
        coverage_start=days[0], coverage_end=days[-1], source_identity='test-calendar'), trading)


def ledger(capital=100000., **kwargs):
    return PhysicalLedger(capital=capital, settlement_calendar=calendar(),
                          policy=QuotePolicy(fee=0., slippage=0.), **kwargs)


def buy(book, key='a', symbol='SPY', right='C', budget=100.):
    contract = symbol+'240524'+right+'00100000'
    fill = dict(contract=contract, side='buy', price=1., sip_timestamp=ns('2024-05-23', '15:00'),
                decision_ns=ns('2024-05-23', '14:59'))
    assert book.buy(key, symbol, fill, equity=book.cash, decision_date=date(2024, 5, 23), budget=budget, security_id='SPY-id')
    return contract


def evidence(contract, price=110.):
    right = contract[-9]
    return dict(metadata=dict(contract=contract, date='2024-05-24', expiry=date(2024, 5, 24),
            underlying=contract[:-15], right=right, strike=100., multiplier=100,
            metadata_receipt_sha256='test-meta'),
        reference=dict(contract=contract, date='2024-05-24', price=price, instruction='exercise-by-exception',
            reference_ns=ns('2024-05-24'), available_ns=ns('2024-05-24', '20:01'),
            exercise_ns=ns('2024-05-24', '21:00'), source_identity='test-official-price', security_id='SPY-id'))


def stock_fill(symbol='SPY', clock=None):
    clock = ns('2024-05-30', '13:30') if clock is None else clock
    return dict(symbol=symbol, side='sell', price=110., provider='alpaca', capture_identity='test-stock', security_id='SPY-id',
                reported_size=1000., decision_ns=clock, sip_timestamp=clock+1_000_000_000)


def test_settlement_transition_and_holiday_are_dated_and_conservative():
    cal = calendar()
    assert cal.settlement(ns('2024-05-24')) == ('2024-05-29', ns('2024-05-30', '13:30'))
    assert cal.settlement(ns('2024-05-28')) == ('2024-05-29', ns('2024-05-30', '13:30'))
    with pytest.raises(ValueError, match='trading or settlement date'):
        cal.settlement(ns('2024-05-27'))
    with pytest.raises(ValueError, match='label horizon'):
        cal.settlement(ns('2024-06-10'))


def test_prior_day_official_price_requires_exact_occ_exception():
    for mode in ('missing', 'wrong_price', 'late', 'valid'):
        book = ledger()
        e = evidence(buy(book))
        ref = e['reference']
        ref['reference_ns'] = ns('2024-05-23')
        if mode != 'missing':
            override = {k: ref[k] for k in ('contract', 'security_id', 'date', 'reference_ns', 'price')}
            override.update(authority='OCC', notice_identity='bound-notice',
                            available_ns=ns('2024-05-24', '19:00'))
            if mode == 'wrong_price':
                override['price'] += 1
            if mode == 'late':
                override['available_ns'] = ns('2024-05-25')
            ref['official_override'] = override
        if mode == 'valid':
            assert book.expire('a', ns('2024-05-24', '21:00'), **e) == 'exercise_committed'
        else:
            with pytest.raises(ValueError, match='evidence required'):
                book.expire('a', ns('2024-05-24', '21:00'), **e)


def cash_evidence(contract, cash=11000.):
    e = evidence(contract)
    e['metadata'].update(settlement_mode='cash_merger', cash_deliverable_per_contract=cash,
                         security_id='SPY-id', effective_ns=ns('2024-05-24', '13:30'),
                         available_ns=ns('2024-05-24', '15:00'))
    e['reference'].update(instruction='cash-exercise-by-exception', cash_deliverable_per_contract=cash)
    return e


@pytest.mark.parametrize('right,cash', [('C', 11000.), ('P', 9000.)])
def test_official_cash_deliverable_does_not_need_shares_or_inject_strike_funding(right, cash):
    book = ledger(capital=1000.)
    contract = buy(book, right=right)
    assert book.expire('a', ns('2024-05-24', '21:00'), **cash_evidence(contract, cash)) == 'cash_exercise_committed'
    assert book.cash == 900. and book.available_cash == 900.
    assert book.equity(ns('2024-05-24', '21:00'), {}) == 1900.
    assert book.positions['a']['phase'] == 'cash_merger_pending' and not book.shares
    book.settle(ns('2024-05-30', '13:30'))
    assert book.cash == 1900. and not book.positions
    assert book.completed['a'] == ns('2024-05-30', '13:30')
    book.reconcile()


def test_cash_merger_does_not_assume_positive_payoff_or_accept_late_terms():
    book = ledger()
    e = cash_evidence(buy(book), 9900.)
    assert book.expire('a', ns('2024-05-24', '21:00'), **e) == 'expired_unexercised'
    assert book.cash == 99900.
    for field, value in [('available_ns', ns('2024-05-25')), ('security_id', 'other-company'),
                          ('cash_deliverable_per_contract', float('nan'))]:
        book = ledger()
        e = cash_evidence(buy(book))
        e['metadata'][field] = value
        with pytest.raises(ValueError, match='cash deliverable'):
            book.expire('a', ns('2024-05-24', '21:00'), **e)
        assert book.cash == 99900. and not book.commitments


def test_funded_call_keeps_slot_and_cash_commitment_until_sale_settles():
    book = ledger()
    contract = buy(book)
    status = book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract))
    assert status == 'exercise_committed'
    assert book.cash == 99900. and book.available_cash == 89900.
    with pytest.raises(ValueError, match='Settled stock'):
        book.liquidate_stock('a', stock_fill())
    book.settle(ns('2024-05-29', '20:00'))
    assert book.positions['a']['phase'] == 'delivery_pending'
    book.settle(ns('2024-05-30', '13:30'))
    assert book.cash == 89900. and book.positions['a']['phase'] == 'stock'
    proceeds = book.liquidate_stock('a', stock_fill())
    assert proceeds == pytest.approx(11000*.9985)
    assert book.cash == 89900. and 'a' in book.positions
    book.settle(ns('2024-06-03', '13:30'))
    assert book.cash == pytest.approx(89900 + 11000*.9985)
    assert not book.positions and book.completed['a'] == ns('2024-06-03', '13:30')
    assert [e.get('kind') for e in book.events] == [None, 'exercise', 'delivery_commitment',
                                                 'settlement', 'stock_delivery', 'stock_sale', 'settlement']
    book.reconcile()


def test_other_entry_reservations_prevent_double_spending_exercise_cash():
    book = ledger(capital=15000.)
    contract = buy(book)
    assert book.reserve_entry('other', 5000.)
    assert book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract)) == 'unresolved_exercise_funding'
    assert book.positions['a']['phase'] == 'option' and not book.commitments
    book.entry_reservations.pop('other')
    assert book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract)) == 'exercise_committed'
    assert not book.reserve_entry('other', 5000.)
    book.reconcile()


def test_put_does_not_create_free_short_stock_and_expiration_is_not_a_fill():
    book = ledger()
    contract = buy(book, right='P')
    assert book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract, 90.)) == 'unresolved_share_delivery'
    assert book.positions and not book.commitments
    other = ledger()
    contract = buy(other)
    assert other.expire('a', ns('2024-05-24', '21:00'), **evidence(contract, 100.)) == 'expired_unexercised'
    assert other.cash == 99900. and not other.positions
    assert other.events[-1]['kind'] == 'expiration_nonexercise'
    assert 'price' not in other.events[-1] and other.events[-1]['cash_delta'] == 0


def test_missing_reference_late_evidence_adjusted_deliverable_rejected():
    for mutate in [lambda e: e['reference'].pop('source_identity'),
                   lambda e: e['reference'].update(available_ns=ns('2024-05-25')),
                   lambda e: e['metadata'].update(multiplier=150)]:
        book = ledger()
        e = evidence(buy(book))
        mutate(e)
        with pytest.raises(ValueError, match='evidence required'):
            book.expire('a', ns('2024-05-24', '21:00'), **e)
        assert len(book.events) == 1


def test_exact_threshold_and_fractional_paper_policy():
    book = ledger()
    contract = buy(book, budget=50.)
    assert book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract, 100.01)) == 'exercise_committed'
    assert book.commitments['a']['shares'] == 50.
    whole = ledger(physical_policy=PhysicalPolicy(fractional_policy='whole-contracts'))
    fill = dict(contract='SPY240524C00100000', side='buy', price=1., sip_timestamp=ns('2024-05-23', '15:00'))
    assert not whole.buy('a','SPY',fill,equity=whole.cash,decision_date=date(2024,5,23),budget=50.,security_id='SPY-id')


def test_stock_quote_requires_actual_provider_size_and_session():
    book = ledger()
    contract = buy(book)
    book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract))
    book.settle(ns('2024-05-30', '13:30'))
    for fill in [dict(stock_fill(), provider='minute-close'), dict(stock_fill(), reported_size=1),
                 stock_fill(clock=ns('2024-05-30', '21:00'))]:
        with pytest.raises(ValueError):
            book.liquidate_stock('a', fill)
    assert book.positions['a']['phase'] == 'stock'
    with pytest.raises(QuoteUnavailable):
        book.equity(ns('2024-05-30', '13:30'), {})


def test_shared_replay_extends_horizon_and_retains_unfunded_outcome():
    class Options:
        def mark(self, contract, clock):
            return dict(bid=1., ask=1., price=1., sip_timestamp=clock)
    class Stocks:
        def mark(self, symbol, clock):
            return dict(bid=110., sip_timestamp=clock, security_id='SPY-id', capture_identity='test-stock')
        def first_fill(self, symbol, clock, **kwargs):
            return stock_fill(symbol, clock)
    context = SimpleNamespace(settlement_calendar=calendar(), policy=PhysicalPolicy(), stock_archive=Stocks(),
        exercise_clock=lambda contract: ns('2024-05-24', '21:00'), expiry_evidence=evidence)
    decision = ns('2024-05-23', '14:59')
    contract = 'SPY240524C00100000'
    proposal = dict(proposal_id='a',symbol='SPY',security_id='SPY-id',decision_ns=decision,score=1.,score_available_ns=decision,
        path=dict(proposal_id='a',capture_complete=True,label_complete=False,label_end_ns=None,
            fills=[dict(contract=contract,side='buy',price=1.,decision_ns=decision,sip_timestamp=decision+1_000_000_000)]))
    clocks = [decision, ns('2024-05-24', '21:00'), ns('2024-05-30', '13:30'), ns('2024-06-03', '13:30')]
    good = portfolio_replay([proposal],clocks,Options(),capital=100000.,fraction=.001,physical=context,
                             policy=QuotePolicy(fee=0.,slippage=0.))
    assert good['complete'] and good['physical_completed_at']['a'] == clocks[-1]
    assert good['cash'] == pytest.approx(89900+11000*.9985)
    blocked = portfolio_replay([proposal],clocks,Options(),capital=100000.,fraction=.1,physical=context)
    assert not blocked['complete'] and blocked['open_positions']['a']['phase'] == 'option'
    assert blocked['decisions'][-1]['status'] == 'unresolved_exercise_funding'


def test_put_delivery_uses_only_previously_funded_settled_inventory():
    book = ledger()
    fill = stock_fill(clock=ns('2024-05-20', '14:00'))
    fill.update(side='buy', price=105.)
    assert book.acquire_inventory('inventory', 'SPY', 'SPY-id', 100., fill)
    book.settle(ns('2024-05-23', '13:30'))
    assert book.shares[('SPY', 'SPY-id')] == 100.
    contract = buy(book, right='P')
    assert book.expire('a', ns('2024-05-24', '21:00'), **evidence(contract, 90.)) == 'exercise_committed'
    assert book.shares[('SPY', 'SPY-id')] == 0.
    before = book.cash
    book.settle(ns('2024-05-30', '13:30'))
    assert book.cash == pytest.approx(before+10000.)
    assert book.cash == pytest.approx(100000-10500*1.0015-100+10000)
    assert not book.positions
    book.reconcile()


def test_competing_exercises_reserve_shared_funds_once():
    book = ledger(capital=15000.)
    first = buy(book)
    second = buy(book, key='b', symbol='QQQ')
    assert book.expire('a', ns('2024-05-24', '21:00'), **evidence(first)) == 'exercise_committed'
    assert book.expire('b', ns('2024-05-24', '21:00'), **evidence(second)) == 'unresolved_exercise_funding'
    assert book.available_cash == 4800.
    book.reconcile()


@pytest.mark.parametrize('holiday,lag,settled,available', [
    ('2022-10-10',2,'2022-10-12','2022-10-13'),
    ('2024-10-14',1,'2024-10-15','2024-10-16'),
])
def test_trading_on_nonsettlement_bank_holiday_counts_from_event_date(holiday,lag,settled,available):
    days=pd.bdate_range(pd.Timestamp(holiday)-pd.Timedelta(days=3),periods=8).strftime('%Y-%m-%d').tolist()
    trading=SessionCalendar(dict(coverage_start=days[0],coverage_end=days[-1],
        sessions=[dict(date=d,open='09:30',close='16:00') for d in days]))
    business=[d for d in days if d!=holiday]
    cal=SettlementCalendar(dict(schema='v7-settlement-calendar-v1',business_dates=business,
        coverage_start=days[0],coverage_end=days[-1],source_identity='test-calendar'),trading)
    assert holiday not in cal.days and trading.bounds(holiday) is not None
    assert cal.settlement(ns(holiday)) == (settled,ns(available,'13:30'))
    # A stock purchase may take place on the banking holiday. The ledger must
    # reserve funding and settle later rather than reject the otherwise valid fill.
    book=PhysicalLedger(settlement_calendar=cal)
    fill=stock_fill(clock=ns(holiday,'13:30'));fill['side']='buy'
    assert book.acquire_inventory('inventory','SPY','SPY-id',10,fill)
    assert book.commitments['inventory']['settled_on']==settled
    assert book.reconcile()['pending_settlements']==1


def test_settlement_rejects_outside_coverage_even_if_trading_calendar_is_longer():
    cal=calendar()
    cal.document['coverage_start']='2024-05-24'
    with pytest.raises(ValueError,match='coverage'):
        cal.settlement(ns('2024-05-23'))
    for invalid in [True,1.5,-1]:
        with pytest.raises(ValueError,match='nanoseconds'):cal.settlement(invalid)
