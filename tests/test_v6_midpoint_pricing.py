import json
import pandas as pd
import pytest
from options.paper_pricing import MIDPOINT_POLICY
from nn_meta.live.v6_portfolio import ForwardPortfolio, COST
from tests import test_v6_forward_portfolio as fixtures


def test_v6_open_legacy_migration_rebases_both_sides_and_is_idempotent(tmp_path):
    book=ForwardPortfolio(tmp_path/'book.sqlite3',scope={'test':True})
    quote=dict(contract='SPY261016C00760000',bid=3.15,ask=3.9,bid_size=10,ask_size=10,
               received_at='2026-09-16T19:00:01Z',sip_timestamp_ns=pd.Timestamp('2026-09-16T19:00Z').value)
    p=dict(key='one',symbol='SPY',state='exit_due',entry_quote=quote,entry_price=3.9*(1+COST),
           contract=quote['contract'],amount=.1,initial_amount=.1,return_factor=1.,rolls=0,legs=[],
           trigger_at='2026-09-16T19:00Z',trigger_reason='underlying strategy exit')
    closed={**p,'key':'closed','state':'closed'}
    with book.connect() as db:
        for obj in (p,closed):db.execute('INSERT INTO positions VALUES (?,?,?,?)',(obj['key'],obj['symbol'],obj['state'],json.dumps(obj)))
    at=pd.Timestamp('2026-09-16T19:00:02Z')
    with pytest.raises(ValueError,match='migration'):book.settle('one',quote_loader=lambda *a,**k:quote,clock=lambda:at)
    preview=book.migrate_midpoint(at=at)
    assert preview['changes'][0]['new_entry_price']==pytest.approx(3.525*(1+COST))
    assert book.open_positions()[0]['entry_price']==p['entry_price']
    assert book.migrate_midpoint(at=at,apply=True)['changes']==preview['changes']
    assert not book.migrate_midpoint(at=at,apply=True)['changes']
    assert book.summary()['equity']==1.
    book.settle('one',quote_loader=lambda *a,**k:quote,clock=lambda:at)
    assert book.summary()['equity']==pytest.approx(1+.1*((1-COST)/(1+COST)-1))
    with book.connect() as db:
        assert json.loads(db.execute("SELECT payload FROM positions WHERE key='closed'").fetchone()[0])==closed
        assert db.execute("SELECT count(*) FROM events WHERE kind='pricing_change'").fetchone()[0]==1


def test_v6_new_midpoint_entry_uses_arithmetic_average():
    fixture=fixtures.ForwardPortfolioTests();fixture.setUp()
    try:
        old=fixture.quote
        fixture.quote=lambda contract,**kwargs:{**old(contract,**kwargs),'mid':2.07,'last':100.}
        fixture.allocate()
        p=fixture.book.open_positions()[0]
        assert p['entry_price']==pytest.approx(2.05*(1+COST))
        assert p['entry_reference']['price_source']=='computed_bid_ask_average'
        assert 'simulated midpoint $2.0500' in fixture.book.entry_payload(p,fixture.bar.tz_localize('UTC'))['message']
    finally:fixture.tearDown()
