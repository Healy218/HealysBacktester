from nn_meta.live.alert_batches import Batches, EXPERTS


class Notify:
    def __init__(self, ok=True):self.sent=[];self.ok=ok
    def send(self,message,title=''):
        if self.ok:self.sent.append(title)
        return self.ok


def payload(i, expert='v4', batch=900):
    return {'title':str(i),'message':'signal','probability':i/100,
            'expert':expert,'alert_cycle':batch}


def finish(queue, batch=900):
    for expert in EXPERTS:queue.complete(expert,batch)


def test_global_top_five_and_no_suppressed_replay(tmp_path):
    q=Batches(tmp_path/'q.db');n=Notify()
    for i in range(1,101):assert q.enqueue(payload(i,list(sorted(EXPERTS))[i%4]),str(i),now=1000)
    assert q.dispatch(n,now=1001)==0
    finish(q)
    assert q.dispatch(n,now=1002)==5
    assert n.sent==['100','99','98','97','96']
    assert q.dispatch(n,now=1003)==0
    q.enqueue(payload(100), 'late',now=1004)
    assert q.dispatch(n,now=1005)==0
    with q.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM candidates WHERE status='suppressed_rank'").fetchone()[0]==95
        assert db.execute("SELECT status FROM candidates WHERE key='late'").fetchone()[0]=='suppressed_late'


def test_small_batch_retry_only_selected_and_idempotent_enqueue(tmp_path):
    q=Batches(tmp_path/'q.db');n=Notify(False)
    for i in range(3):
        q.enqueue(payload(i),str(i),now=1000);q.enqueue(payload(i),str(i),now=1000)
    finish(q)
    assert q.dispatch(n,now=1001)==0
    n.ok=True
    assert q.dispatch(n,now=1002)==3
    assert q.dispatch(n,now=1003)==0


def test_missing_expert_deadline_expiry_and_unrankable(tmp_path):
    q=Batches(tmp_path/'q.db');n=Notify()
    assert not q.enqueue(dict(payload(1),probability=float('nan')),'bad',now=1000)
    assert not q.enqueue({'title':'old','message':'old'},'legacy',now=1000)
    q.enqueue(payload(50),'one',now=1000)
    assert q.dispatch(n,now=1299)==0
    assert q.dispatch(n,now=1300)==1
    q.enqueue(payload(70,batch=1800),'two',now=1900)
    finish(q,1800)
    assert q.dispatch(n,now=2800)==0


class API:
    chat='123'
    def __init__(self):self.calls=[];self.updates=[]
    def call(self,method,**payload):
        self.calls.append((method,payload))
        if method=='getUpdates':return [u for u in self.updates if u['update_id']>=payload['offset']]
        if method=='sendMessage':return {'message_id':99}
        return True


def test_overflow_button_reply_routing_and_duplicate_updates(tmp_path):
    from nn_meta.live.alert_replies import publish_notices, poll_replies, requested_batch
    q=Batches(tmp_path/'q.db');n=Notify();api=API()
    for i in range(10):q.enqueue(payload(i),str(i),now=1000)
    finish(q);q.dispatch(n,now=1001)
    publish_notices(q,api);publish_notices(q,api)
    assert len(api.calls)==1
    note=api.calls[0][1]
    assert '5 more alerts' in note['text']
    assert note['reply_markup']['inline_keyboard'][0][0]['callback_data']=='alerts:900'
    update={'update_id':1,'callback_query':{'id':'cb','data':'alerts:900',
            'message':{'message_id':99,'chat':{'id':123}}}}
    assert requested_batch(q,update,'456') is None
    api.updates=[update]
    poll_replies(q,api);poll_replies(q,api)
    texts=[p['text'] for m,p in api.calls if m=='sendMessage']
    assert len(texts)==2
    assert 'Remaining alerts' in texts[-1]
    assert '4.0%' in texts[-1] and '9.0%' not in texts[-1]
    yes={'message':{'text':'yes','reply_to_message':{'message_id':99},'chat':{'id':123}}}
    assert requested_batch(q,yes,'123')==900
    yes['message']['reply_to_message']['message_id']=100
    assert requested_batch(q,yes,'123') is None


def test_summary_chunks_stay_within_telegram_limit(tmp_path):
    from nn_meta.live.alert_replies import summary_parts
    q=Batches(tmp_path/'q.db')
    for i in range(100):q.enqueue(dict(payload(i),summary='symbol strategy '+('x'*280)),str(i),now=1000)
    finish(q);q.dispatch(Notify(),now=1001)
    parts=summary_parts(q,900)
    assert len(parts)>1
    assert all(len(p)<=3500 for p in parts)
    assert sum(p.count('%') for p in parts)==95
