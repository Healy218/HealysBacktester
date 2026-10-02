import json
from pathlib import Path
import shutil
import sqlite3
import pytest
from nn_meta.v7.storage import identity,sha,receipt
from nn_meta.v7 import checkpoint_clone_v1 as clone
from scripts.run_v7_optimized_campaign_v1 import command,select_wave
from scripts import lab_hourly_watch as watch


def seed(tmp_path):
    parent=tmp_path/'parent';source=parent/'securities/SID';source.mkdir(parents=True)
    (parent/'lock').touch()
    plan=tmp_path/'plan';job=plan/'jobs/SID';job.mkdir(parents=True)
    (job/'complete.json').write_text('{}')
    index=parent/'indexes/SID';index.mkdir(parents=True)
    (index/'payload.json').write_text('{}');receipt(index,{})
    old=dict(inputs={},securities=['SID'],plan=str(plan),entry_root='entry')
    (parent/'declaration.json').write_text(json.dumps(old))
    binding=dict(campaign_identity=identity(old),jobs_sha256=sha(job/'complete.json'),quote_index_sha256=sha(index/'complete.json'))
    (source/'binding.json').write_text(json.dumps(binding))
    with sqlite3.connect(source/'wave.sqlite3') as db:
        db.execute('CREATE TABLE data(value)');db.execute('INSERT INTO data VALUES(7)')
    return parent,old


def test_import_survives_interrupted_directory_publication(tmp_path,monkeypatch):
    parent,old=seed(tmp_path);out=tmp_path/'out';out.mkdir()
    # tmpfs does not support reflinks: test the publication protocol independently.
    monkeypatch.setattr(clone,'clone_file',shutil.copy2)
    original=Path.rename
    def interrupted(src,dst):
        if src.name=='securities':raise InterruptedError('power loss')
        return original(src,dst)
    monkeypatch.setattr(Path,'rename',interrupted)
    with pytest.raises(InterruptedError):clone.inherit_checkpoint(parent,out,old,'SID')
    assert (out/'indexes').exists() and not (out/'inherited-checkpoint.json').exists()
    monkeypatch.setattr(Path,'rename',original)
    doc=clone.inherit_checkpoint(parent,out,old,'SID')
    assert doc['parent']==str(parent)
    with sqlite3.connect(out/'securities/SID/wave.sqlite3') as db:db.execute('UPDATE data SET value=8')
    with sqlite3.connect(parent/'securities/SID/wave.sqlite3') as db:assert db.execute('SELECT value FROM data').fetchone()==(7,)
    assert clone.inherit_checkpoint(parent,out,old,'SID')==doc


def test_changed_scientific_input_rejected(tmp_path,monkeypatch):
    parent,old=seed(tmp_path);f=tmp_path/'frozen.json';f.write_text('{}')
    old['inputs'][str(f)]=sha(f)
    (parent/'declaration.json').write_text(json.dumps(old))
    with pytest.raises(ValueError,match='scientific input changed'):
        clone.inherit_checkpoint(parent,tmp_path/'out',{**old,'inputs':{}},'SID')


def test_selected_wave_replaces_counts_without_losing_parent(tmp_path):
    state=tmp_path/'state';(state/'waves').mkdir(parents=True)
    for name,n in [('parent',10),('successor',15)]:
        p=tmp_path/name;p.mkdir();(p/'progress.json').write_text(json.dumps(dict(status='checkpointed',cohorts_discovered=n,distinct_horizon_targets_covered=n*5)))
    select_wave(state,'SID',tmp_path/'parent')
    assert watch.wave_work(state/'waves','discovered')['cohorts_processed']==10
    (state/'waves/SID.next').symlink_to(tmp_path/'successor',target_is_directory=True)
    assert watch.wave_work(state/'waves','discovered')['cohorts_processed']==10
    select_wave(state,'SID',tmp_path/'successor')
    assert watch.wave_work(state/'waves','discovered')['cohorts_processed']==15
    assert json.loads((tmp_path/'parent/progress.json').read_text())['cohorts_discovered']==10


def test_commands_keep_parent_on_repeated_slices(tmp_path):
    parent=tmp_path/'old/waves/SID';parent.mkdir(parents=True);(parent/'declaration.json').write_text('{}')
    config=dict(mode='replay',arguments={'plan':'jobs'},parent=str(tmp_path/'old'))
    c=command(tmp_path/'new',config,'SID',600)
    assert 'replay_v7_pending_wave_v3.py' in c[2]
    assert c[c.index('--checkpoint-from')+1]==str(parent)
    assert c[c.index('--output')+1]==str(tmp_path/'new/revisions/SID')


def test_watcher_uses_explicit_successor(tmp_path,monkeypatch):
    monkeypatch.setattr(watch,'STATE',tmp_path)
    selection=dict(required='/required',discovery='/discovery',initial_replay='/initial')
    (tmp_path/'v7-selection.json').write_text(json.dumps(selection))
    assert watch.v7_locations()==tuple(map(Path,['/required','/discovery','/discovery','/initial']))
