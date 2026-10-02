import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import time
import msgpack
import pytest
from scripts import record_v6_alpaca_options_v1 as recorder

S='SPY261002C00660000'
def plan(tmp_path,contracts=None):
    p=tmp_path/'plan.json';p.write_text(json.dumps(dict(scope='transport_validation_only',model_admission=False,contracts=contracts or [S])))
    return p

def test_no_silent_subscription_truncation(tmp_path):
    contracts=[f'SPY261002C{x:08d}' for x in range(1001)]
    with pytest.raises(ValueError,match='never truncate'):recorder.load_plan(plan(tmp_path,contracts))

def test_recorder_cannot_self_admit_features(tmp_path):
    p=plan(tmp_path);d=json.loads(p.read_text());d['model_admission']=True;p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='not been admitted'):recorder.load_plan(p)

@pytest.mark.parametrize('wrong_ack',[False,True])
def test_acknowledged_raw_recording_and_mismatch(tmp_path,monkeypatch,wrong_ack):
    done=[False];sent=[];now=time.time_ns()
    packets=[
        [{'T':'success','msg':'authenticated'}],
        [{'T':'subscription','quotes':[] if wrong_ack else [S],'trades':[S]}],
        [{'T':'q','S':S,'t':msgpack.Timestamp((now-1000000)//10**9,(now-1000000)%10**9),'bp':1.,'ap':1.2,'bs':5,'as':6,'c':'A'},
         {'T':'t','S':S,'t':msgpack.Timestamp((now-500000)//10**9,(now-500000)%10**9),'p':1.2,'s':2,'c':'I'}]]
    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def send(self,data):sent.append(msgpack.unpackb(data,raw=False))
        async def recv(self):
            packet=packets.pop(0)
            if not packets:done[0]=True
            return msgpack.packb(packet)
    monkeypatch.setattr(recorder.websockets,'connect',lambda *a,**k:Socket())
    monkeypatch.setattr(recorder,'time',SimpleNamespace(time_ns=time.time_ns,monotonic_ns=time.monotonic_ns,monotonic=lambda:10 if done[0] else 0))
    monkeypatch.setenv('ALPACA_PAPER_API_KEY','fake');monkeypatch.setenv('ALPACA_PAPER_API_SECRET','fake')
    root=tmp_path/'capture'
    if wrong_ack:
        with pytest.raises(ValueError,match='acknowledgement'):asyncio.run(recorder.capture(plan(tmp_path),root,5))
    else:asyncio.run(recorder.capture(plan(tmp_path),root,5))
    status=json.loads((root/'status.json').read_text())
    assert not status['model_admission'] and not status['coverage_complete']
    assert status['status']==('interrupted' if wrong_ack else 'finished')
    assert sent[1]==dict(action='subscribe',quotes=[S],trades=[S])
    if not wrong_ack:
        assert status['journal']['fsynced_rows']==2
        rows=[json.loads(x) for x in next(root.glob('*/journal/*/quotes.jsonl')).read_text().splitlines()]
        assert rows[0]['event_timestamp_ns']==now-1000000
        assert rows[0]['condition_namespace']=='alpaca_opra_string'
        assert rows[0]['receipt_basis']=='websocket_handler_after_msgpack_decode'
