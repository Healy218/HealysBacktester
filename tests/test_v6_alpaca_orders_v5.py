from datetime import timedelta
from decimal import Decimal
import json
import sqlite3

import pytest

from integrations.alpaca_paper.v6_bridge_v5 import Journal, process_events, available_cash
from integrations.alpaca_paper.v6_pricing_v4 import execution_limit, step_limit
from tests.test_v6_alpaca_runtime import Broker, Data, NOW, FP, entry, close


def setup(tmp_path):
    return Journal(tmp_path/'orders.sqlite3'), Broker(), Data()


def poll(events, j, b, d, seconds=0, submit=True):
    d.at = NOW + timedelta(seconds=seconds)
    return process_events(events,journal=j,trading=b,data=d,expected_fingerprint=FP,
                          submit=submit,now=d.at)


def plans(j):
    return [json.loads(j.get(r['event_id'])['payload'])['plan'] for r in j.all()]


@pytest.mark.parametrize('side,expected', [
    ('buy',['3.27','3.43','3.50']), ('sell',['2.95','2.79','2.72'])])
def test_fixed_midpoint_steps_and_rounding(side,expected):
    q=dict(bid='2.77',ask='3.45',mark='3.40',bid_size=10,ask_size=10,
        sip_timestamp_ns=int(NOW.timestamp()*1e9),received_at=NOW.isoformat())
    result=execution_limit(q,now=NOW,after=NOW,side=side)
    assert result['step_limits']==expected and result['midpoint']=='3.11'
    with pytest.raises(ValueError,match='stale'):
        execution_limit(q,now=NOW+timedelta(seconds=31),after=NOW,side=side)
    with pytest.raises(ValueError):step_limit('.01','sell',2)


def test_all_three_steps_waits_restart_and_final_cancel(tmp_path):
    j,b,d=setup(tmp_path);e=entry()
    poll([e],j,b,d)
    for cancel_at,replace_at in [(30,31),(61,62)]:
        before=b.posts
        poll([e],j,b,d,cancel_at-1);assert b.posts==before
        poll([e],j,b,d,cancel_at);assert b.posts==before
        j=Journal(j.path)
        poll([e],j,b,d,replace_at);assert b.posts==before+1
    poll([e],j,b,d,121);assert len(b.cancels)==2
    poll([e],j,b,d,122);assert len(b.cancels)==3
    poll([e],j,b,d,123);poll([e],j,b,d,200)
    assert b.posts==3 and j.chains()[e['event_id']]['state']=='done'
    assert [p['limit_price'] for p in plans(j)]==['2.21','2.31','2.37']
    assert [p['cancel_after_seconds'] for p in plans(j)]==[30,30,60]
    assert len({r['client_order_id'] for r in j.all()})==3


def test_partial_fill_replacement_only_remaining_and_anchor_never_moves(tmp_path):
    j,b,d=setup(tmp_path);e=entry()
    poll([e],j,b,d);b.fill(3)
    poll([e],j,b,d,30)
    d.bid=3;d.ask=3.2
    poll([e],j,b,d,31)
    assert plans(j)[-1]['qty']==7 and plans(j)[-1]['limit_price']=='2.31'
    b.fill()
    poll([e],j,b,d,32)
    assert Decimal(b.positions[e['contract']].qty)==10
    assert b.posts==2 and j.chains()[e['event_id']]['state']=='done'


def test_pending_cancel_blocks_replacement_but_independent_orders_continue(tmp_path):
    j,b,d=setup(tmp_path);e=entry();other=entry('two','MSFT261002C00300000')
    poll([e],j,b,d)
    def cancel(oid):
        b.cancels.append(oid)
        next(o for o in b.orders.values() if o.id==oid).status='pending_cancel'
    b.cancel_order_by_id=cancel
    poll([e,other],j,b,d,30)
    poll([e,other],j,b,d,31)
    assert b.posts==2 and len(b.cancels)==1
    first=list(b.orders.values())[0];first.status='canceled'
    poll([e,other],j,b,d,32)
    assert b.posts==3 and plans(j)[-1]['step']==1


def test_full_fill_during_cancel_never_rebuys(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d)
    b.cancel_order_by_id=lambda _:b.fill()
    poll([e],j,b,d,30);poll([e],j,b,d,31)
    assert b.posts==1 and j.chains()[e['event_id']]['state']=='done'


def test_external_cancel_and_reject_never_start_replacement(tmp_path):
    for status in ['canceled','rejected','expired']:
        p=tmp_path/status;p.mkdir();j,b,d=setup(p);e=entry()
        poll([e],j,b,d);list(b.orders.values())[0].status=status
        poll([e],j,b,d,31)
        assert b.posts==1 and j.chains()[e['event_id']]['state']=='done'


def test_partial_buy_is_canceled_before_superseding_exit(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);b.fill(3)
    poll([close(e),e],j,b,d,5)
    assert b.posts==1 and b.cancels
    poll([close(e),e],j,b,d,6)
    assert b.posts==2 and plans(j)[-1]['side']=='sell' and plans(j)[-1]['qty']==3
    b.fill();poll([close(e),e],j,b,d,7)
    assert not b.positions and b.posts==2


def test_sell_ladder_accounts_for_partial_closes(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);b.fill()
    poll([close(e),e],j,b,d,1);b.fill(2)
    poll([close(e),e],j,b,d,31)
    poll([close(e),e],j,b,d,32)
    assert plans(j)[-1]['qty']==8
    assert [p['limit_price'] for p in plans(j) if p['side']=='sell']==['1.99','1.89']
    b.fill();poll([close(e),e],j,b,d,33)
    assert not b.positions


def test_size_and_reservation_use_maximum_buy_price(tmp_path):
    j,b,d=setup(tmp_path);b.account.cash=b.account.options_buying_power='9000';e=entry()
    poll([e],j,b,d)
    assert plans(j)[0]['qty']==3  # four would fit first step but exceed final allocation
    rows={r['client_order_id']:r for r in j.all()}
    assert available_cash(b.account,rows,j)==Decimal('8289')
    poll([e],j,b,d,30)
    from integrations.alpaca_paper.v6_bridge import reconcile
    _,_,rows=reconcile(j,b,expected_fingerprint=FP,allow_pending=True)
    assert available_cash(b.account,rows,j)==Decimal('8289')  # cancel gap still reserved


def test_ambiguous_replacement_is_not_duplicated_after_restart(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);poll([e],j,b,d,30)
    def unknown(order_data):b.posts+=1;raise ConnectionError('ambiguous POST')
    b.submit_order=unknown
    with pytest.raises(ConnectionError):poll([e],j,b,d,31)
    with pytest.raises(ValueError,match='cannot be resolved'):poll([e],Journal(j.path),b,d,32)
    assert b.posts==2 and j.all()[-1]['state']=='uncertain_post'


def test_stale_replacement_and_stale_restart_never_send(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);poll([e],j,b,d,30)
    original=d.get_option_snapshot
    def stale(request):
        result=original(request);result[e['contract']].latest_quote.timestamp=NOW
        return result
    d.get_option_snapshot=stale
    assert poll([e],j,b,d,31)[0]['status']=='replacement_blocked'
    poll([e],j,b,d,301)
    assert b.posts==1 and j.chains()[e['event_id']]['state']=='done'


def test_original_entry_deadline_does_not_truncate_admitted_ladder(tmp_path):
    j,b,d=setup(tmp_path);e=entry();e['signal_close']=(NOW-timedelta(seconds=590)).isoformat()
    poll([e],j,b,d);poll([e],j,b,d,30);poll([e],j,b,d,31)
    assert b.posts==2


def test_preview_has_no_chain_order_or_cancel_writes(tmp_path):
    j,b,d=setup(tmp_path);e=entry()
    assert poll([e],j,b,d,submit=False)[0]['status']=='preview'
    assert not j.all() and not j.chains() and b.posts==0
    poll([e],j,b,d);poll([e],j,b,d,30,submit=False)
    assert not b.cancels


def test_scanner_preserves_active_chain_during_cancel_gap(tmp_path):
    from tests.test_v6_source_reconcile import setup as source_setup, NOW as source_now
    from integrations.alpaca_paper.v6_source_reconcile_v2 import retire_unfilled_sources
    database,oldj,e,payload=source_setup(tmp_path)
    j=Journal(oldj.path)
    j.save_chain(dict(event=e,state='active',plan={}))
    assert not retire_unfilled_sources(database,j,{}, {},now=source_now)
    j.save_chain(dict(event=e,state='done',plan={}))
    assert len(retire_unfilled_sources(database,j,{}, {},now=source_now))==1


def test_legacy_v2_order_keeps_timeout_without_new_ladder(tmp_path):
    from integrations.alpaca_paper.v6_bridge_v2 import process_events as old
    j,b,d=setup(tmp_path);e=entry()
    old([e],journal=j,trading=b,data=d,expected_fingerprint=FP,submit=True,now=NOW)
    poll([e],j,b,d,30);assert not b.cancels
    poll([e],j,b,d,120);assert len(b.cancels)==1
    poll([e],j,b,d,121);assert b.posts==1 and not j.chains()


def test_crash_before_first_intent_does_not_bypass_entry_deadline(tmp_path):
    j,b,d=setup(tmp_path);e=entry();e['signal_close']=(NOW-timedelta(seconds=590)).isoformat()
    plan=poll([e],j,b,d,submit=False)[0]['plan']
    j.save_chain(dict(event=e,plan=plan,state='active'))
    poll([e],j,b,d,31)
    assert b.posts==0 and j.chains()[e['event_id']]['state']=='done'


def test_replacement_respects_reduced_buying_power(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);poll([e],j,b,d,30)
    b.account.options_buying_power='100'
    result=poll([e],j,b,d,31)
    assert b.posts==1 and result[0]['status']=='replacement_blocked'


def test_same_poll_cash_limit_survives_instant_fills_and_lagging_balances(tmp_path):
    j,b,d=setup(tmp_path);b.account.cash=b.account.options_buying_power='10000'
    original=b.submit_order
    def instant(order_data):
        order=original(order_data);b.fill();return order
    b.submit_order=instant
    events=[entry(str(i),contract=f'AAPL261002C{200000+i*1000:08d}') for i in range(30)]
    poll(events,j,b,d)
    assert sum(Decimal(p['step_limits'][-1])*p['qty']*100 for p in plans(j)) <= Decimal('10000')


def test_same_contract_and_roll_dependency_survive_step_cancellation(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);b.fill(2)
    poll([e],j,b,d,30)
    new=entry('different',e['contract']);roll=entry('one','AAPL261009C00200000',roll=1)
    result=poll([e,new,roll],j,b,d,31)
    assert b.posts==2  # only the original remainder advances
    assert sum(r['status']=='awaiting_dependency' for r in result)==2


def test_final_sell_timeout_keeps_actual_remaining_position(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d);b.fill()
    poll([close(e),e],j,b,d,1)
    for cancel,replace in [(31,32),(62,63)]:
        poll([close(e),e],j,b,d,cancel);poll([close(e),e],j,b,d,replace)
    poll([close(e),e],j,b,d,154);poll([close(e),e],j,b,d,155)
    poll([close(e),e],j,b,d,170)
    assert b.posts==4 and Decimal(b.positions[e['contract']].qty)==10
    assert j.chains()[close(e)['event_id']]['state']=='done'


def test_partial_fill_during_cancel_reduces_replacement(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d)
    original=b.cancel_order_by_id
    def cancel(oid):b.fill(4);original(oid)
    b.cancel_order_by_id=cancel
    poll([e],j,b,d,30);poll([e],j,b,d,31)
    assert plans(j)[-1]['qty']==6


def test_v5_dispatcher_requires_explicit_policy_admission(tmp_path):
    from scripts.run_v6_alpaca_runtime_v5 import validate
    (tmp_path/'paper-restart.json').write_text(json.dumps(dict(
        schema='v6-alpaca-paper-restart-prepared-v1',historical_positions_imported=False,
        activated_at=NOW.isoformat(),scanner_enabled=True,bridge_runtime_sha256={},
        execution_policy='midpoint-concession-2pct-120s-v2')))
    with pytest.raises(ValueError,match='not admitted'):validate(tmp_path)


def test_upgrade_keeps_inflight_v3_four_step_prices_and_waits(tmp_path):
    from integrations.alpaca_paper.v6_bridge_v3 import process_events as old
    j,b,d=setup(tmp_path);e=entry()
    old([e],journal=j,trading=b,data=d,expected_fingerprint=FP,submit=True,now=NOW)
    for cancel_at,replace_at in [(30,31),(61,62),(92,93)]:
        poll([e],j,b,d,cancel_at);poll([e],Journal(j.path),b,d,replace_at)
    assert [p['limit_price'] for p in plans(j)]==['2.16','2.21','2.26','2.31']
    assert [p['cancel_after_seconds'] for p in plans(j)]==[30,30,30,60]
    poll([e],j,b,d,152);assert len(b.cancels)==3
    poll([e],j,b,d,153);poll([e],j,b,d,154)
    assert b.posts==4 and j.chains()[e['event_id']]['state']=='done'


def test_inconsistent_saved_policy_fails_closed(tmp_path):
    j,b,d=setup(tmp_path);e=entry();poll([e],j,b,d)
    chain=j.chains()[e['event_id']];chain['plan']['step_waits']=[1,1,1];j.save_chain(chain)
    with pytest.raises(ValueError,match='waits differ'):poll([e],j,b,d,30)
    assert not b.cancels and b.posts==1


def test_actual_axp_and_vg_anchor_sell_prices():
    assert [step_limit('11.45','sell',s) for s in range(3)]==['10.87','10.30','10.01']
    assert [step_limit('.80','sell',s) for s in range(3)]==['0.76','0.72','0.70']
