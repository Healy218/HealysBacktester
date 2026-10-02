import os
from scripts import v7_discovery_resources_v4 as policy
from tests.test_v7_discovery_resources_v3 import size


def test_worker_thread_limit_does_not_cap_process_pool(monkeypatch):
    monkeypatch.setenv('OMP_NUM_THREADS','1');monkeypatch.setenv('OMP_THREAD_LIMIT','1')
    seen={}
    def check(command,**kwargs):
        seen.update(kwargs['env']);return '8\n'
    monkeypatch.setattr(policy.subprocess,'check_output',check)
    result=policy.admission(12,available_mib=30000,own_mib=4000,paper_mib=0,incubator_mib=0,replay_mib=512,cpus=16)
    assert result['admitted_workers']==8
    assert 'OMP_NUM_THREADS' not in seen and 'OMP_THREAD_LIMIT' not in seen
    assert os.environ['OMP_NUM_THREADS']=='1' and os.environ['OMP_THREAD_LIMIT']=='1'
