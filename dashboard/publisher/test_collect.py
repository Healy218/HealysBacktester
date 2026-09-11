from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from collect import collect_server,collect_home,scanner,market,queue,connect,positions
from publish import envelope
NOW=datetime(2026,9,11,15,tzinfo=timezone.utc)

def test_missing_sources_stay_unknown_and_database_not_created(tmp_path):
    s=collect_server(tmp_path,NOW)
    assert not s['queueAvailable'] and not s['positionsAvailable'] and s['market']=='unknown'
    assert not (tmp_path/'nn_meta/live/.alert_batches.sqlite3').exists()

def test_scanner_does_not_call_queued_delivered(tmp_path):
    p=tmp_path/'v4.log';p.write_text('2026-09-11 14:45:02,001 - x filtered (score too low)\n[v4] scanned 118 · alerted 4 · delivered 3 · errors 1\n2026-09-11 14:59:55,000 starting next pass\n')
    s=scanner(p,'v4');assert s['queued']==3 and s['errors']==1
    assert s['lastCompletionAt']=='2026-09-11T14:45:02+00:00' and s['observedAt']=='2026-09-11T14:59:55+00:00'

def test_calendar_holiday_earlyclose_and_out_of_coverage(tmp_path):
    p=tmp_path/'cal.json';p.write_text(json.dumps({'sessions':[{'date':'2026-09-04','open':'09:30','close':'16:00'},{'date':'2026-09-11','open':'09:30','close':'13:00'}]}))
    assert market(p,NOW)=='open'
    assert market(p,datetime(2026,9,11,17,tzinfo=timezone.utc))=='closed'
    assert market(p,datetime(2026,9,7,15,tzinfo=timezone.utc))=='closed'
    assert market(p,datetime(2026,9,12,15,tzinfo=timezone.utc))=='unknown'

def test_queue_counts_entire_day_but_bounds_detail_and_connection_readonly(tmp_path):
    p=tmp_path/'queue.db';db=sqlite3.connect(p)
    db.execute('CREATE TABLE candidates(key,trade_ref,symbol,side,expert,score,status,batch,trade_context)')
    for i in range(105):db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?)',(str(i),str(i),'AAPL','BUY CALL','v4',.7,'sent' if i<100 else 'pending',NOW.timestamp()-60,'{}'))
    db.commit();db.close();before=p.read_bytes()
    ro=connect(p);counts,rows=queue(ro,NOW)
    assert counts=={'sent':100,'pending':5} and len(rows)==100
    with pytest.raises(sqlite3.OperationalError):ro.execute('DELETE FROM candidates')
    ro.close();assert before==p.read_bytes()

def test_missing_home_and_oversize_publisher(tmp_path):
    h=collect_home(tmp_path,now=NOW);assert h['fa']['symbols'] is None and h['research'] is None
    assert envelope(h)['fields']['payload']['stringValue']
    with pytest.raises(ValueError):envelope(dict(observedAt=NOW.isoformat(),value='a'*800000))

def test_partial_sale_unknown_fees_never_becomes_zero_net(tmp_path):
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE taken_trades(id,context,quantity,fill_price,status,taken_at,last_checked,exit_notice,monitor_error,actual_entry_fees)')
    db.execute('CREATE TABLE taken_sales(update_id,trade_id,quantity,premium,fees)')
    db.execute('INSERT INTO taken_trades VALUES(?,?,?,?,?,?,?,?,?,?)',('id',json.dumps({'symbol':'PTON','contract':'PTON260918P00005000'}),4,1.0,'open',NOW.timestamp(),None,None,None,'2.00'))
    db.execute('INSERT INTO taken_sales VALUES(1,"id",2,"1.50",NULL)')
    p=positions(db,{})[0];assert p['remaining']==2 and p['realizedGross']==100 and p['realizedNet'] is None
    db.execute('UPDATE taken_sales SET fees="1.00"');assert positions(db,{})[0]['realizedNet']==98


def test_exit_due_is_active_in_server_summary(tmp_path):
    folder=tmp_path/'nn_meta/live';folder.mkdir(parents=True)
    db=sqlite3.connect(folder/'.alert_batches.sqlite3')
    db.execute('CREATE TABLE taken_trades(id,context,quantity,fill_price,status,taken_at,last_checked,exit_notice,monitor_error,actual_entry_fees)')
    db.execute('CREATE TABLE taken_sales(update_id,trade_id,quantity,premium,fees)')
    db.execute('INSERT INTO taken_trades VALUES(?,?,?,?,?,?,?,?,?,?)',('id',json.dumps({'symbol':'PTON','contract':'PTON260918P00005000'}),4,1.0,'exit_due',NOW.timestamp(),None,None,None,None))
    db.commit();db.close()
    s=collect_server(tmp_path,NOW)
    assert s['positionsAvailable'] and s['openPositionCount']==1
    assert s['positions'][0]['status']=='exit_due'
