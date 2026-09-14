import json
from pathlib import Path
import tempfile
import unittest

from nn_meta.live.alert_batches import Batches, EXPERTS
from nn_meta.live.v6_alert_bridge import ingest, publish_notices


class Notifier:
    def __init__(self): self.sent=[]
    def send(self,message,title=None): self.sent.append((title,message)); return True


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.queue=Batches(self.root/'queue.sqlite3'); self.spool=self.root/'spool'; self.spool.mkdir()
        self.notifier=Notifier(); self.cycle=1800000000
    def tearDown(self): self.temp.cleanup()
    def event(self,kind='entry'):
        payload=dict(expert='v6',probability=.7,alert_cycle=self.cycle,symbol='SPY',side='BUY CALL',
            title='[v6] SPY BUY CALL',message='EXPERIMENTAL PAPER')
        event=dict(schema='v6-forward-alert-v1',experimental=True,key='v6|SPY|test|bar',kind=kind,payload=payload,
                   created_at='2026-09-14T13:49:00+00:00')
        (self.spool/'event.json').write_text(json.dumps(event))
        return event
    def test_v6_paper_entry_delivers_after_legacy_cycle_finishes(self):
        for expert in EXPERTS: self.queue.complete(expert,self.cycle)
        self.assertEqual(self.queue.dispatch(self.notifier,now=self.cycle+29),0)
        self.event(); self.assertEqual(ingest(self.queue,self.spool,now=self.cycle+30),1)
        self.assertEqual(self.queue.dispatch(self.notifier,now=self.cycle+31),0)
        self.assertEqual(publish_notices(self.queue,self.notifier),1)
        self.assertEqual(ingest(self.queue,self.spool,now=self.cycle+33),0)
        self.assertEqual(publish_notices(self.queue,self.notifier),0)
    def test_legacy_does_not_wait_for_v6(self):
        event=self.event(); p=dict(event['payload'],expert='v3')
        self.queue.enqueue(p,'v3|test',now=self.cycle+20)
        for expert in EXPERTS: self.queue.complete(expert,self.cycle)
        self.assertEqual(self.queue.dispatch(self.notifier,now=self.cycle+21),1)
    def test_notices_are_deduplicated_and_mutated_events_fail(self):
        event=self.event('notice'); ingest(self.queue,self.spool,now=self.cycle)
        self.assertEqual(publish_notices(self.queue,self.notifier),1)
        self.assertEqual(publish_notices(self.queue,self.notifier),0)
        event['payload']['message']='changed'; (self.spool/'event.json').write_text(json.dumps(event))
        with self.assertRaisesRegex(ValueError,'changed'): ingest(self.queue,self.spool)


if __name__=='__main__': unittest.main()
