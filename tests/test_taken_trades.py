import json
import time

import pytest

from nn_meta.live.alert_batches import Batches, EXPERTS
from nn_meta.live.taken_trades import context_for, handle, trade_id

OCC = 'MARA351009C00011500'


def queued(tmp_path, notifier=None):
    q = Batches(tmp_path / 'q.db')
    ctx = context_for('MARA', strategy='rsi', params={'rsi_window':14,'entry_threshold':35,'exit_threshold':70}, direction=0, spot=11.73, entry_ts='2026-09-09 16:30', sim_start='2026-07-10 13:30')
    q.enqueue(dict(title='[v31] MARA BUY CALL',message='real alert',probability=.58,expert='v31',alert_cycle=900,contract=OCC,trade_context=ctx), 'key', now=1000)
    with q.connect() as db:
        db.execute('INSERT INTO trade_messages VALUES (?,?)',(42,'key'))
    return q, trade_id('key')


def message(text, uid=1, reply=None, chat=123):
    m=dict(text=text,chat={'id':chat},date=time.time())
    if reply:
        m['reply_to_message']={'message_id':reply}
    return dict(update_id=uid,message=m)


def callback(ident, uid=1, mid=42, chat=123):
    return dict(update_id=uid,callback_query=dict(id='cb',data='taken:'+ident,message=dict(message_id=mid,chat={'id':chat})))


def rows(q):
    with q.connect() as db:
        return db.execute('SELECT * FROM taken_trades').fetchall()


def test_button_reply_manual_fill_and_close(tmp_path):
    q, ident=queued(tmp_path)
    assert 'Added to your sell list' in handle(q,callback(ident),'123')
    assert rows(q)[0]['fill_price'] is None
    assert 'already' in handle(q,message('taken',2,reply=42),'123')
    assert 'Fill updated' in handle(q,message(f'/taken {ident} 2 @ 1.35',3),'123')
    assert len(rows(q))==1 and rows(q)[0]['quantity']==2 and rows(q)[0]['fill_price']==1.35
    listing=handle(q,message('/selllist',4),'123')
    assert OCC in listing and '2 @ $1.35' in listing
    assert 'marked closed' in handle(q,message(f'/sold {ident}',5),'123')
    assert 'empty' in handle(q,message('/selllist',6),'123')
    assert 'already marked sold' in handle(q,message(f'/taken {ident}',7),'123')


def test_manual_command_creates_with_actual_fill(tmp_path):
    q,ident=queued(tmp_path)
    assert 'Taken' in handle(q,message(f'/taken {ident} 3@1.40'),'123')
    assert rows(q)[0]['quantity']==3
    ctx=json.loads(rows(q)[0]['context'])
    assert ctx['params']['exit_threshold']==70 and ctx['contract']==OCC


@pytest.mark.parametrize('text', ['taken 0 @ 1.35','taken 2 @ -1','taken nonsense','taken 1 @ nan'])
def test_invalid_fills_do_not_create_positions(tmp_path,text):
    q,_=queued(tmp_path)
    handle(q,message(text,reply=42),'123')
    assert not rows(q)


def test_wrong_chat_or_forged_button_does_not_mutate(tmp_path):
    q,ident=queued(tmp_path)
    assert handle(q,callback(ident,chat=999),'123') is None
    assert 'not linked' in handle(q,callback(ident,mid=99),'123')
    assert not rows(q)


def test_override_must_match_symbol_and_right(tmp_path):
    q,ident=queued(tmp_path)
    assert 'match' in handle(q,message(f'/taken {ident} contract SPY351009C00100000'),'123')
    assert not rows(q)
    assert 'Taken' in handle(q,message(f'/taken {ident} contract MARA351009C00012000',2),'123')
    assert json.loads(rows(q)[0]['context'])['contract'].endswith('00012000')


def test_retry_after_confirmation_failure_does_not_repeat_mutation(tmp_path):
    from nn_meta.live.alert_replies import poll_replies
    from tests.test_alert_batches import API
    class Fails(API):
        failed=False
        def call(self,method,**kw):
            if method=='sendMessage' and not self.failed:
                self.failed=True
                raise RuntimeError('temporary')
            return super().call(method,**kw)
    q,ident=queued(tmp_path);api=Fails();api.updates=[callback(ident)]
    with pytest.raises(RuntimeError):poll_replies(q,api)
    assert len(rows(q))==1
    poll_replies(q,api);poll_replies(q,api)
    assert len(rows(q))==1
    assert len([c for c in api.calls if c[0]=='sendMessage'])==1


def test_dispatch_attaches_button_and_stores_message_mapping(tmp_path):
    q,ident=queued(tmp_path)
    class Notifier:
        def send_trade_alert(self,message,title,tid):
            assert tid==ident
            return 56
    for expert in EXPERTS:q.complete(expert,900)
    assert q.dispatch(Notifier(),now=1001)==1
    with q.connect() as db:
        assert db.execute('SELECT candidate_key FROM trade_messages WHERE message_id=56').fetchone()[0]=='key'
    assert 'Taken' in handle(q,message('taken',reply=56),'123')


def test_additive_migration_preserves_existing_candidates(tmp_path):
    import sqlite3
    path=tmp_path/'q.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE candidates(key TEXT PRIMARY KEY,batch INTEGER,expert TEXT,score REAL,title TEXT,message TEXT,status TEXT,summary TEXT)')
        db.execute("INSERT INTO candidates VALUES ('old',900,'v3',.6,'old','old','sent','old')")
    q=Batches(path)
    with q.connect() as db:
        assert db.execute("SELECT message FROM candidates WHERE key='old'").fetchone()[0]=='old'
    assert 'lacks' in handle(q,message('/taken '+trade_id('old')),'123')


def test_old_original_reply_recovers_matching_frozen_rule(tmp_path, monkeypatch):
    from nn_meta import config
    q,ident=queued(tmp_path)
    label='entry=35, exit=70, window=14'
    folder=tmp_path/'artifacts_v31';folder.mkdir()
    spec={'symbols':{'MARA':{'strategies':{'rsi':{'params':{'rsi_window':14,'entry_threshold':35,'exit_threshold':70},'param_label':label,'dte':30}}}}}
    (folder/'baseline_spec.json').write_text(json.dumps(spec))
    monkeypatch.setattr(config,'ROOT',tmp_path)
    body=f'[v31] MARA: BUY CALL\ntrigger: rsi ({label})\ncontract: MARA 2035-10-09 $11.50 CALL ({OCC})\nbar: 2026-09-09 16:30:00 UTC · spot $11.73'
    with q.connect() as db:
        db.execute("UPDATE candidates SET status='sent',message=?,symbol='MARA',side='BUY CALL',trade_context=NULL",(body,))
    update=message('taken',reply=1234)
    update['message']['reply_to_message']['text']='🔔 old title\n'+body
    assert 'Added' in handle(q,update,'123')
    ctx=json.loads(rows(q)[0]['context'])
    assert ctx['contract']==OCC and ctx['warmup_date_only']
    assert ctx['params']['exit_threshold']==70


def test_telegram_button_payload_and_message_id():
    from nn_meta.live.notifier import TelegramNotifier
    class Session:
        def post(self,url,**kw):
            assert kw['json']['reply_markup']['inline_keyboard'][0][0]['callback_data']=='taken:ABC'
            assert 'Trade ID: ABC' in kw['json']['text']
            class Response:
                status_code=200
                def json(self):return {'ok':True,'result':{'message_id':77}}
            return Response()
    assert TelegramNotifier('test','123',Session()).send_trade_alert('body','title','ABC')==77


def test_quantity_without_premium_is_preserved_and_displayed(tmp_path):
    q,ident=queued(tmp_path)
    response=handle(q,message(f'/taken {ident} 5 contract MARA351009C00012000'),'123')
    assert 'Quantity: 5 contracts' in response
    assert rows(q)[0]['quantity']==5 and rows(q)[0]['fill_price'] is None
    assert '5 contracts · fill price not recorded' in handle(q,message('/selllist',uid=2),'123')
    handle(q,message(f'/taken {ident} 5 @ 1.35',uid=3),'123')
    handle(q,message(f'/taken {ident} 4',uid=4),'123')
    assert rows(q)[0]['quantity']==4 and rows(q)[0]['fill_price']==1.35

@pytest.fixture
def contract_clock(monkeypatch):
    from datetime import datetime, timezone
    import nn_meta.live.taken_trades as taken
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 11, 19, tzinfo=timezone.utc)
    monkeypatch.setattr(taken, 'datetime', Clock)


@pytest.mark.parametrize('reply', [True, False])
def test_short_contract_override_records_actual_fill_and_preserves_alert(tmp_path, contract_clock, reply):
    q, ident = queued(tmp_path)
    text = '/taken ' + ('' if reply else ident + ' ') + '1 9/16 72C @ 1.03'
    update = message(text, reply=42 if reply else None)
    response = handle(q, update, '123')
    assert 'Taken — MARA260916C00072000' in response
    row = rows(q)[0]
    assert row['quantity'] == 1 and row['fill_price'] == 1.03
    assert json.loads(row['context'])['contract'] == 'MARA260916C00072000'
    assert json.loads(row['context'])['params']['exit_threshold'] == 70
    assert handle(q, update, '123') == response
    with q.connect() as db:
        original = json.loads(db.execute('SELECT trade_context FROM candidates').fetchone()[0])
        assert original['contract'] == OCC
        assert db.execute('SELECT COUNT(*) FROM taken_accounting_events').fetchone()[0] == 1


@pytest.mark.parametrize('value,occ', [
    ('2 9/16/2027 72.5c @ .95', 'MARA270916C00072500'),
    ('2 9/16/27 $72.125 C@1.03', 'MARA270916C00072125'),
    ('2 9/16 72C', 'MARA260916C00072000'),
])
def test_short_override_date_decimal_and_quantity_only(tmp_path, contract_clock, value, occ):
    q, _ = queued(tmp_path)
    assert 'Taken' in handle(q, message('/taken ' + value, reply=42), '123')
    assert json.loads(rows(q)[0]['context'])['contract'] == occ


@pytest.mark.parametrize('value', [
    '1 9/16 72P @ 1.03', '1 2/30 72C @ 1.03',
    '1 9/10 72C @ 1.03', '1 9/16 72.0001C @ 1.03',
    '1 9/16 0C @ 1.03', '1 9/16 100000C @ 1.03',
    '0 9/16 72C @ 1.03', '1 9/16 72C @ 0',
    '1 9/16 72C @ nan', '1 9/16 72C @ 1.03 extra',
    '1 9/16/1968 72C @ 1.03', '1 9/16 72C @ 1.03 contract MARA351009C00072000',
])
def test_invalid_short_override_never_creates_position(tmp_path, contract_clock, value):
    q, _ = queued(tmp_path)
    handle(q, message('/taken ' + value, reply=42), '123')
    assert not rows(q)
    with q.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM taken_accounting_events').fetchone()[0] == 0


def test_short_override_does_not_guess_alert_or_change_existing_contract(tmp_path, contract_clock):
    q, ident = queued(tmp_path)
    assert 'Trade ID not found' in handle(q, message('/taken 1 9/16 72C @ 1.03'), '123')
    assert not rows(q)
    handle(q, message(f'/taken {ident} 1 @ 1.03', uid=2), '123')
    assert 'already tracks a different contract' in handle(q, message('/taken 1 9/16 72C @ 1.03', uid=3, reply=42), '123')
    assert json.loads(rows(q)[0]['context'])['contract'] == OCC
    assert rows(q)[0]['quantity'] == 1


def test_short_override_corrects_button_placeholder_and_keeps_strategy(tmp_path, contract_clock):
    q, ident = queued(tmp_path)
    handle(q, callback(ident), '123')
    original = json.loads(rows(q)[0]['context'])
    response = handle(q, message('/taken 1 9/16 72C @ 1.03', uid=2, reply=42), '123')
    assert 'Contract corrected: MARA260916C00072000' in response
    assert 'Fill: 1 @ $1.03' in response
    row = rows(q)[0]
    expected = dict(original, contract='MARA260916C00072000')
    assert json.loads(row['context']) == expected
    assert row['id'] == ident and row['quantity'] == 1 and row['fill_price'] == 1.03
    assert len(rows(q)) == 1


@pytest.mark.parametrize('field,value', [('quantity', 1), ('fill_price', 1.03),
    ('actual_entry_fees', '0.10'), ('status', 'exit_due'), ('exit_notice', 'Exit now')])
def test_contract_correction_rejects_nonplaceholder_positions(tmp_path, contract_clock, field, value):
    q, ident = queued(tmp_path)
    handle(q, callback(ident), '123')
    with q.connect() as db:
        db.execute(f'UPDATE taken_trades SET {field}=? WHERE id=?', (value, ident))
    before = dict(rows(q)[0])
    assert 'already tracks a different contract' in handle(q, message('/taken 1 9/16 72C @ 1.03', uid=2, reply=42), '123')
    assert dict(rows(q)[0]) == before
