from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest
from scripts import run_v6_freeze_trial as t


def test_baseline_and_review():
    def row(hour,count):
        return {'time_utc':f'2026-09-07T{hour:02}:00:00+00:00',
                'processes':[{'stage':'freeze'}]*4,'counts':{'freeze_shards':count}}
    b=t.baseline_rate([row(8,0),row(10,10),row(11,20),row(12,30)])
    assert b['average_per_hour']==10
    assert t.reviewed_workers(10,10)==4
    assert t.reviewed_workers(11,10)==5
    with pytest.raises(ValueError):t.baseline_rate([row(12,30)])


def test_trial_five_slots_and_completed_shard_reuse(tmp_path,monkeypatch):
    pending=[];live=set();peak=0;starts=[]
    class Process:
        def __init__(self, command, **kwargs):
            nonlocal peak
            self.symbol=command[command.index('--symbols')+1]
            self.path=Path(command[command.index('--out')+1]);self.pid=100+len(starts)
            starts.append(self.symbol);live.add(self.symbol);peak=max(peak,len(live))
        def poll(self):
            live.discard(self.symbol);self.path.write_text('{}');return 0
        def wait(self):return self.poll()
    monkeypatch.setattr(t.subprocess,'Popen',Process)
    monkeypatch.setattr(t,'available_bytes',lambda:12*1024**3)
    monkeypatch.setattr(t,'memory_pressure',lambda:0)
    monkeypatch.setattr(t.time,'sleep',lambda n:None)
    monkeypatch.setattr(t.research,'validate_shards',lambda *a:None)
    labels=['A','B','C','D','E','F','G']
    (tmp_path/'A.json').write_text('retained')
    commands=[['python','-m','nn_meta.freeze_baseline','--symbols',s,'--out',str(tmp_path/f'{s}.json')] for s in labels]
    trial=t.Trial(tmp_path,{'average_per_hour':10},2)
    trial.parallel(commands,workers=5,environment={},cwd=tmp_path,log_dir=tmp_path,labels=labels)
    assert peak==5
    assert starts==labels[1:]
    assert (tmp_path/'A.json').read_text()=='retained'
    assert json.loads((tmp_path/'status.json').read_text())['completed']==6


def test_memory_guard_starts_only_four(tmp_path,monkeypatch):
    class Stop(Exception):pass
    trial=t.Trial(tmp_path,{'average_per_hour':10},2)
    monkeypatch.setattr(t,'available_bytes',lambda:3*1024**3)
    monkeypatch.setattr(t,'memory_pressure',lambda:0)
    monkeypatch.setattr(t.time,'sleep',lambda n:(_ for _ in ()).throw(Stop()))
    monkeypatch.setattr(t.subprocess,'Popen',lambda *a,**k:pytest.fail('low headroom must not launch'))
    with pytest.raises(Stop):
        trial.parallel([['python','-m','nn_meta.freeze_baseline','--out',str(tmp_path/'A.json')]],
                       workers=5,environment={},cwd=tmp_path,log_dir=tmp_path,labels=['A'])
    state=json.loads((tmp_path/'status.json').read_text())
    assert state['target_workers']==4
    assert state['decision']=='return_to_four_memory_headroom'
