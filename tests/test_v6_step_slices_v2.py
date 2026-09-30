from decimal import Decimal
from datetime import timedelta

from integrations.alpaca_paper.v6_step_slices_v2 import process_events,Journal
from tests.test_v6_alpaca_runtime import Broker, Data, NOW, FP, entry, close


def poll(events,j,b,d,seconds):
    d.at=NOW+timedelta(seconds=seconds)
    return process_events(events,journal=j,trading=b,data=d,expected_fingerprint=FP,submit=True,now=d.at)


def test_successful_slices_eventually_close_full_holding_and_unblock_roll(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry()
    poll([e],j,b,d,0);b.fill()
    d.bid_size=4
    events=[close(e),e,entry('one','AAPL261009C00200000',roll=1)]
    poll(events,j,b,d,1);b.fill()
    assert Decimal(b.positions[e['contract']].qty)==6
    poll(events,j,b,d,2);poll(events,j,b,d,3);b.fill()
    assert Decimal(b.positions[e['contract']].qty)==2
    poll(events,j,b,d,4);poll(events,j,b,d,5);b.fill()
    poll(events,j,b,d,6)
    assert e['contract'] not in b.positions
    assert b.posts==5 and list(b.orders.values())[-1].symbol=='AAPL261009C00200000'
    assert len({r['client_order_id'] for r in j.all()})==5


def test_failed_final_sell_step_never_restarts_as_new_slice(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry()
    poll([e],j,b,d,0);b.fill();poll([close(e),e],j,b,d,1)
    for cancel,replace in [(31,32),(62,63)]:
        poll([close(e),e],j,b,d,cancel);poll([close(e),e],j,b,d,replace)
    poll([close(e),e],j,b,d,154);poll([close(e),e],j,b,d,155)
    poll([close(e),e],j,b,d,170)
    assert b.posts==4 and len(j.chains())==2 and Decimal(b.positions[e['contract']].qty)==10


def legacy_exhausted(tmp_path, partial=0):
    from integrations.alpaca_paper.v6_bridge_v3 import process_events as legacy
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry();c=close(e)
    def old(seconds):
        d.at=NOW+timedelta(seconds=seconds)
        return legacy([c,e] if seconds else [e],journal=j,trading=b,data=d,
                      expected_fingerprint=FP,submit=True,now=d.at)
    old(0);b.fill();old(1)
    if partial:b.fill(partial)
    for t in [31,32,62,63,93,94,154,155]:old(t)
    return j,b,d,e,c


def retry_poll(j,b,d,e,c,seconds):
    d.at=NOW+timedelta(seconds=seconds)
    return process_events([c,e],journal=j,trading=b,data=d,expected_fingerprint=FP,
        submit=True,now=d.at,approved_exit_retries=[c['event_id']])


def test_approved_legacy_retry_uses_fresh_anchor_remaining_and_unique_ids_once(tmp_path):
    import json
    from integrations.alpaca_paper.v6_step_slices_v2 import retry_id
    j,b,d,e,c=legacy_exhausted(tmp_path,partial=2)
    original=j.chains()[c['event_id']]
    d.bid=3;d.ask=3.2
    retry_poll(j,b,d,e,c,200)
    plan=json.loads(j.get(j.all()[-1]['event_id'])['payload'])['plan']
    assert plan['midpoint']=='3.1' and plan['limit_price']=='2.94' and plan['qty']==8
    assert plan['event_id']==retry_id(c['event_id'])
    for t in [230,231,261,262,322,323,400,500]:
        j=Journal(j.path);retry_poll(j,b,d,e,c,t)
    assert b.posts==8 and Decimal(b.positions[e['contract']].qty)==8
    assert j.chains()[c['event_id']]==original
    assert len({r['client_order_id'] for r in j.all()})==8
    assert j.chains()[retry_id(c['event_id'])]['state']=='done'


def test_approved_retry_keeps_successful_liquidity_slicing_and_stops_at_flat(tmp_path):
    j,b,d,e,c=legacy_exhausted(tmp_path)
    d.bid_size=4
    for t in [200,202,204]:
        retry_poll(j,b,d,e,c,t);b.fill();retry_poll(j,b,d,e,c,t+1)
    retry_poll(j,b,d,e,c,206)
    assert not b.positions and b.posts==8


def test_unapproved_exhausted_legacy_exit_is_not_rearmed(tmp_path):
    j,b,d,e,c=legacy_exhausted(tmp_path)
    poll([c,e],j,b,d,200)
    assert b.posts==5
