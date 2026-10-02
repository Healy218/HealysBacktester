from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.v7_discovery_resources_v3 import admission


def size(hour=13,minute=0,**changes):
    args=dict(now=datetime(2026,10,2,hour,minute,tzinfo=ZoneInfo('America/Chicago')),
        available_mib=26000,own_mib=1000,paper_mib=0,incubator_mib=0,replay_mib=512,cpus=16,autosized=99)
    args.update(changes)
    return admission(12,**args)


def test_resident_workers_do_not_reduce_total_pool_twice():
    assert size()['admitted_workers']==9
    assert size(available_mib=22000,own_mib=5000)['admitted_workers']==9


def test_paper_growth_consumes_its_reserved_allowance():
    assert size(available_mib=18000,paper_mib=8000)['admitted_workers']==size()['admitted_workers']


def test_zero_and_cpu_service_caps():
    assert size(available_mib=12000)['admitted_workers']==0
    assert size(hour=22,available_mib=30000)['admitted_workers']==12
    assert size(hour=22,cpus=8)['admitted_workers']==6


def test_daily_reserve_begins_before_slices_can_cross_start():
    assert size(hour=15,minute=30)['reserve_mib']>size()['reserve_mib']
    assert size(hour=22,incubator_mib=10000,available_mib=16000)['reserve_mib']==size(hour=16,incubator_mib=10000,available_mib=16000)['reserve_mib']


def test_scheduler_resource_revision_preserves_existing_declaration(tmp_path,monkeypatch):
    import json
    from scripts import run_v7_optimized_campaign_v1 as old
    from scripts import run_v7_optimized_campaign_v2 as new
    path=tmp_path/'declaration.json';path.write_text('{"unchanged": true}\n')
    before=path.read_bytes()
    monkeypatch.setattr(old,'prepare',lambda *a:dict(inputs={'original':'digest'}))
    result=new.prepare(tmp_path,tmp_path/'config.json')
    assert path.read_bytes()==before
    assert result['inputs']['original']=='digest'
    revision=json.loads((tmp_path/'resource-revision-v2.json').read_text())
    assert revision['scientific_workers_unchanged']
    assert new.prepare(tmp_path,tmp_path/'config.json')==result


def test_larger_observed_working_sets_reduce_new_admission():
    observed=size(own_mib=6000,active_workers=4)
    assert observed['per_worker_mib']==2304
    assert observed['admitted_workers']<=5
