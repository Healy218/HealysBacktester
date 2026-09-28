from decimal import Decimal
from datetime import timedelta

from integrations.alpaca_paper.v6_step_slices import process_events,Journal
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
    for cancel,replace in [(31,32),(62,63),(93,94)]:
        poll([close(e),e],j,b,d,cancel);poll([close(e),e],j,b,d,replace)
    poll([close(e),e],j,b,d,154);poll([close(e),e],j,b,d,155)
    poll([close(e),e],j,b,d,170)
    assert b.posts==5 and len(j.chains())==2 and Decimal(b.positions[e['contract']].qty)==10
