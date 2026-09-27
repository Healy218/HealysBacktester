import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from nn_meta.v7.storage import identity,verify
from nn_meta.v7.packed_quotes_v2 import write_pack
from nn_meta.v7.packed_quote_index import write_index,IndexedQuoteArchive
from scripts.v7_capture_storage import RESERVE,METADATA_RESERVATION,route,publish_locator,physical_bytes,expand_quota,verify_mount
from scripts.run_v7_capture_campaign_v4 import acquire,reuse
from scripts.run_v7_capture_campaign_v3 import pack_binding
from scripts import v7_parallel_capture_v4 as parallel
from tests.test_v7_parallel_capture_v3 import items,capture
from options.data.massive_ticks import MassiveTicks


def test_routing_counts_every_inflight_write_and_preserves_reserve():
    task=1024**3
    assert route(RESERVE+4*task,RESERVE+4*task,['local']*3,task)=='local'
    assert route(RESERVE+4*task-1,RESERVE+task,['local']*3,task)=='external'
    assert route(RESERVE+METADATA_RESERVATION-1,RESERVE+task,[],task) is None
    assert route(RESERVE+METADATA_RESERVATION,RESERVE+task,[],task)=='external'
    assert route(RESERVE+METADATA_RESERVATION,RESERVE+task-1,[],task) is None
    assert route(RESERVE+10*task,RESERVE+task,[],task,force_external=True)=='external'


def test_file_locator_is_discoverable_verified_and_readable_through_index(tmp_path):
    requested=items(1);item=requested[0]
    rows,manifest=capture(None,**{k:item[k] for k in ('contract','kind','start_ns','end_ns')})
    external=tmp_path/'external'/'pack';logical=tmp_path/'local'/'sid'/'pack'
    write_pack(external,[(item,rows,manifest)],binding={})
    publish_locator(logical,external)
    assert not logical.is_symlink() and (logical/'captures.sqlite3').is_symlink()
    assert verify(logical)==verify(external)
    assert list((tmp_path/'local').rglob('complete.json'))==[logical/'complete.json']
    assert physical_bytes(logical)==sum((logical/name).stat().st_size for name in ('binding.json','complete.json'))
    write_index(tmp_path/'index',[logical],binding={})
    with IndexedQuoteArchive(tmp_path/'index') as archive:
        assert archive.window(item['contract'],'quotes',1,100)[0]==rows
    publish_locator(logical,external)
    (external/'captures.sqlite3').rename(external/'offline')
    with pytest.raises(FileNotFoundError):verify(logical)


def test_quota_amendment_keeps_usage_and_refuses_live_reservations(tmp_path):
    q=dict(limit_bytes=100,used_bytes=20,reservations={})
    (tmp_path/'quota.json').write_text(json.dumps(q))
    result=expand_quota(tmp_path,200,authorization='fixture')
    assert result['after']['limit_bytes']==220 and result['after']['used_bytes']==20
    q['reservations']={'active':10};(tmp_path/'quota.json').write_text(json.dumps(q))
    with pytest.raises(ValueError,match='Drain'):expand_quota(tmp_path,300,authorization='fixture')
    assert json.loads((tmp_path/'quota.json').read_text())==q


def test_wrong_drive_or_missing_mount_is_rejected(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess,'check_output',lambda *a,**k:json.dumps(dict(filesystems=[dict(target=str(tmp_path),uuid='wrong',options='rw')])) )
    with pytest.raises(ValueError,match='Authorized overflow'):verify_mount(tmp_path,'expected')


@pytest.fixture
def storage_job(tmp_path,monkeypatch):
    import scripts.v7_capture_storage as storage
    monkeypatch.setattr(storage,'verify_mount',lambda *a: {})
    monkeypatch.setenv('MASSIVE_API_KEY','fixture')
    monkeypatch.setattr(MassiveTicks,'capture',capture)
    monkeypatch.setattr(parallel,'prefetch_limit',lambda n:2)
    budget=tmp_path/'budget';budget.mkdir()
    (budget/'quota.json').write_text(json.dumps(dict(limit_bytes=20*1024**3,used_bytes=0,reservations={})))
    requested=items(8);binding=pack_binding({},requested,'fixture',{})
    job=dict(logical=str(budget/'pack'),physical=str(tmp_path/'external'/'pack'),budget=str(budget),binding=binding,
        parents=[],items=requested,io_threads=32,attempts=str(tmp_path/'attempts'),tier='external',mount=str(tmp_path/'external'),mount_uuid='fixture')
    with ThreadPoolExecutor(max_workers=4) as pool:
        monkeypatch.setattr(parallel,'_POOL',pool)
        yield job


def test_overflow_capture_and_resume_are_charged_once(storage_job):
    job=storage_job
    assert acquire(job)['status']=='completed'
    quota=json.loads((Path(job['budget'])/'quota.json').read_text())
    assert not quota['reservations']
    assert quota['used_bytes']==physical_bytes(job['logical'])+physical_bytes(job['physical'])
    assert verify(job['logical'])['captures']==len(job['items'])
    assert acquire(job)['status']=='reused'
    assert json.loads((Path(job['budget'])/'quota.json').read_text())==quota


def test_external_publication_failure_recovers_without_fetching_or_recharging_payload(storage_job,monkeypatch):
    import scripts.v7_capture_storage as storage
    job=storage_job;publish=storage.publish_locator
    def fail(*a):raise OSError('fixture disconnected after physical publication')
    monkeypatch.setattr(storage,'publish_locator',fail)
    assert acquire(job)['status']=='failed'
    assert Path(job['physical']).exists() and not Path(job['logical']).exists()
    before=json.loads((Path(job['budget'])/'quota.json').read_text())['used_bytes']
    monkeypatch.setattr(storage,'publish_locator',publish)
    def no_fetch(*a,**k):raise AssertionError('recovery must not reacquire')
    monkeypatch.setattr(MassiveTicks,'capture',no_fetch)
    report=acquire(job)
    assert report['status']=='completed' and report['recovered_external_pack']
    after=json.loads((Path(job['budget'])/'quota.json').read_text())
    assert after['used_bytes']-before==physical_bytes(job['logical']) and not after['reservations']


def test_prior_versions_require_exact_source_binding(tmp_path):
    requested=items(1);item=requested[0];prior=pack_binding({},requested,'fixture',{'old':'sha'})
    root=tmp_path/'pack';write_pack(root,[(item,*capture(None,**{k:item[k] for k in ('contract','kind','start_ns','end_ns')}))],binding=prior)
    new=pack_binding({},requested,'fixture',{})
    assert reuse(root,new,[(prior['schema'],prior['sources'])])
    with pytest.raises(ValueError):reuse(root,new,[])
