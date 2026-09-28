from datetime import timedelta
from decimal import Decimal
import json

import pytest

from integrations.alpaca_paper.v6_bridge_v2 import Journal, process_events, available_cash
from integrations.alpaca_paper.v6_pricing_v2 import execution_limit
from tests.test_v6_alpaca_runtime import Broker, Data, NOW, FP, entry, close


def poll(events, j, b, d, seconds=0, submit=True):
    d.at = NOW + timedelta(seconds=seconds)
    return process_events(events, journal=j, trading=b, data=d, expected_fingerprint=FP,
                          submit=submit, now=d.at)


def setup(tmp_path):
    return Journal(tmp_path/'orders.sqlite3'), Broker(), Data()


def other(key='two', roll=0):
    return entry(key, contract='MSFT261002C00300000', roll=roll)


@pytest.mark.parametrize('side,expected', [('buy','3.18'), ('sell','3.04')])
def test_adjusted_midpoint_rounding(side, expected):
    quote = dict(bid='2.77', ask='3.45', mark='3.40', last='3.41', bid_size=10, ask_size=10,
                 sip_timestamp_ns=int(NOW.timestamp()*1e9), received_at=NOW.isoformat())
    result = execution_limit(quote, now=NOW, after=NOW, side=side)
    assert result['limit_price'] == expected
    assert result['midpoint'] == '3.11'
    with pytest.raises(ValueError, match='stale'):
        execution_limit(quote, now=NOW+timedelta(seconds=31), after=NOW, side=side)


def test_rounding_can_cross_touch_but_never_zero_sell():
    quote = dict(bid='1.00', ask='1.00', bid_size=10, ask_size=10,
                 sip_timestamp_ns=int(NOW.timestamp()*1e9), received_at=NOW.isoformat())
    assert execution_limit(quote, now=NOW, after=NOW, side='buy')['limit_price']=='1.02'
    quote.update(bid='.01',ask='.01')
    with pytest.raises(ValueError, match='positive'):
        execution_limit(quote, now=NOW, after=NOW, side='sell')


def test_two_orders_same_poll_pending_first_does_not_block_second(tmp_path):
    j,b,d=setup(tmp_path)
    result=poll([entry(),other()],j,b,d)
    assert b.posts==2 and [r['status'] for r in result]==['new','new']
    for row in j.all():
        plan=json.loads(j.get(row['event_id'])['payload'])['plan']
        assert plan['limit_price']=='2.15' and plan['cancel_after_seconds']==120
    poll([entry(),other()],Journal(j.path),b,d,seconds=15)
    assert b.posts==2


def test_timeout_boundary_and_pending_cancel_keeps_dependencies(tmp_path):
    j,b,d=setup(tmp_path);e=entry()
    poll([e],j,b,d)
    poll([e],j,b,d,seconds=119)
    assert not b.cancels
    def pending_cancel(order_id):
        b.cancels.append(order_id)
        next(o for o in b.orders.values() if o.id==order_id).status='pending_cancel'
    b.cancel_order_by_id=pending_cancel
    result=poll([close(e),e,other()],j,b,d,seconds=120)
    assert len(b.cancels)==1 and b.posts==2
    assert any(r['status']=='awaiting_dependency' for r in result)
    poll([close(e),e,other()],j,b,d,seconds=135)
    assert b.posts==2 and len(b.cancels)==1


def test_same_contract_and_roll_block_but_unrelated_entry_proceeds(tmp_path):
    j,b,d=setup(tmp_path);e=entry()
    result=poll([e, entry('duplicate'), other('one',roll=1), other()],j,b,d)
    assert b.posts==2
    assert sum(r['status']=='awaiting_dependency' for r in result)==2


def test_unrelated_exit_is_not_blocked_and_duplicate_close_is_blocked(tmp_path):
    j,b,d=setup(tmp_path);e=entry();f=other()
    poll([f],j,b,d);b.fill()
    poll([e],j,b,d)
    result=poll([close(f),dict(close(f),event_id='second-close'),e],j,b,d)
    assert b.posts==3 and list(b.orders.values())[-1].side=='sell'
    assert any(r['status']=='awaiting_dependency' for r in result)
    plan=json.loads(j.get(close(f)['event_id'])['payload'])['plan']
    assert plan['limit_price']=='2.05'


def test_pending_buy_reservations_not_double_subtracted_from_broker_bp(tmp_path):
    j,b,d=setup(tmp_path)
    b.account.cash='10000';b.account.options_buying_power='10000'
    poll([entry()],j,b,d)
    # Four contracts at $2.15 => $860 held. BP already includes that hold.
    b.account.options_buying_power='9140'
    assert available_cash(b.account,{r['client_order_id']:r for r in j.all()},j)==Decimal('9140')
    result=poll([other()],j,b,d)
    assert b.posts==2 and list(b.orders.values())[-1].qty=='4.0'
    assert result[-1]['status']=='new'


def test_partial_fill_reserves_only_remainder(tmp_path):
    j,b,d=setup(tmp_path)
    poll([entry()],j,b,d);b.fill(3)
    b.account.cash='99370';b.account.options_buying_power='97865'
    poll([],j,b,d)
    assert available_cash(b.account,{r['client_order_id']:r for r in j.all()},j)==Decimal('97865')


def test_same_poll_budget_survives_lagging_cash_after_instant_fills(tmp_path):
    j,b,d=setup(tmp_path)
    b.account.cash='10000';b.account.options_buying_power='10000'
    submit=b.submit_order
    def instant(order_data):
        order=submit(order_data);b.fill();return order
    b.submit_order=instant
    events=[entry(str(i),contract=f'AAPL261002C{200000+i*1000:08d}') for i in range(30)]
    poll(events,j,b,d)
    spent=sum(Decimal(json.loads(j.get(r['event_id'])['payload'])['plan']['limit_price'])*r['quantity']*100
              for r in j.all())
    assert spent<=Decimal('10000')
    assert any(r['quantity']<4 for r in j.all())


def test_ambiguous_post_stops_submissions_and_never_duplicates(tmp_path):
    j,b,d=setup(tmp_path)
    def uncertain(order_data):
        b.posts+=1;raise ConnectionError('unknown POST outcome')
    b.submit_order=uncertain
    with pytest.raises(ConnectionError):poll([entry(),other()],j,b,d)
    assert b.posts==1 and j.all()[0]['state']=='uncertain_post'
    with pytest.raises(ValueError,match='cannot be resolved'):
        poll([entry(),other()],j,b,d)
    assert b.posts==1


def test_preview_reserves_hypothetical_orders_without_mutation(tmp_path):
    j,b,d=setup(tmp_path)
    result=poll([entry(),entry('duplicate'),other()],j,b,d,submit=False)
    assert [r['status'] for r in result]==['preview','awaiting_dependency','preview']
    assert not j.all() and b.posts==0


def test_buy_size_uses_adjusted_limit(tmp_path):
    j,b,d=setup(tmp_path)
    b.account.cash='8500';b.account.options_buying_power='8500'
    poll([entry()],j,b,d)
    assert j.all()[0]['quantity']==3  # midpoint 2.10 would incorrectly allow four


def test_legacy_orders_retain_recorded_policy_at_cutover(tmp_path):
    from integrations.alpaca_paper.v6_bridge import process_events as legacy
    j,b,d=setup(tmp_path)
    legacy([entry()],journal=j,trading=b,data=d,expected_fingerprint=FP,submit=True,now=NOW)
    poll([],j,b,d,seconds=60)
    assert len(b.cancels)==1


def test_cancel_race_and_rejection_do_not_duplicate_or_sell_other_position(tmp_path):
    j,b,d=setup(tmp_path);e=entry()
    poll([e],j,b,d)
    def fills_during_cancel(order_id):
        b.fill()
    b.cancel_order_by_id=fills_during_cancel
    poll([close(e),other()],j,b,d,seconds=120)
    # Reconciliation after the independent POST discovers the fill.
    poll([close(e),e,other()],j,b,d,seconds=121)
    assert b.posts==3 and list(b.orders.values())[-1].side=='sell'
    assert Decimal(list(b.orders.values())[-1].qty)==10


def test_foreign_order_blocks_all_new_submissions(tmp_path):
    j,b,d=setup(tmp_path)
    poll([entry()],j,b,d)
    list(b.orders.values())[0].client_order_id='foreign'
    with pytest.raises(ValueError,match='unrecognized'):
        poll([other()],j,b,d)
    assert b.posts==1


def test_fresh_broker_bp_lower_than_cash_caps_next_order(tmp_path):
    j,b,d=setup(tmp_path)
    submit=b.submit_order
    def lower_bp(order_data):
        order=submit(order_data)
        b.account.options_buying_power='1000'
        return order
    b.submit_order=lower_bp
    result=poll([entry(),other()],j,b,d)
    assert b.posts==1 and result[-1]['status']=='blocked'


def test_v2_dispatcher_refuses_unadmitted_policy(tmp_path):
    from scripts.run_v6_alpaca_runtime_v2 import validate
    (tmp_path/'paper-restart.json').write_text(json.dumps(dict(
        schema='v6-alpaca-paper-restart-prepared-v1', historical_positions_imported=False,
        activated_at=NOW.isoformat(), scanner_enabled=True, bridge_runtime_sha256={})))
    with pytest.raises(ValueError,match='not admitted'):
        validate(tmp_path)
