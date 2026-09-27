"""Preserve old receipts and quota accounting across the worker-count upgrade."""
import json
from pathlib import Path

import pytest

from nn_meta.v7.storage import verify
from scripts.run_v7_capture_campaign_v5 import acquire as old_acquire
from scripts.run_v7_capture_campaign_v6 import acquire, reuse
from scripts import run_v7_capture_campaign_v7 as twelve
from scripts.run_v7_capture_campaign_v3 import pack_binding
from tests.test_v7_capture_memory import storage_job


@pytest.mark.parametrize('old_acquire,acquire,reuse', [
    (old_acquire, acquire, reuse),
    (acquire, twelve.acquire, twelve.reuse),
])
def test_new_runner_reuses_prior_pack_without_refetch_or_recharge(storage_job, monkeypatch, old_acquire, acquire, reuse):
    from options.data.massive_ticks import MassiveTicks
    job = storage_job
    assert old_acquire(job)['status'] == 'completed'
    receipt = verify(job['logical'])
    quota_path = Path(job['budget']) / 'quota.json'
    before = quota_path.read_bytes()
    prior = job['binding']
    job = dict(job, binding=pack_binding({}, job['items'], 'fixture', {}),
               parents=[(prior['schema'], prior['sources'])])
    # Different bound computation identity, while preserving the prior scope.
    job['binding']['sources'] = {str(Path(__file__)): __import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest()}
    def no_fetch(*a, **k):
        raise AssertionError('completed data must be reused')
    monkeypatch.setattr(MassiveTicks, 'capture', no_fetch)
    assert acquire(job)['status'] == 'reused'
    assert quota_path.read_bytes() == before
    assert verify(job['logical']) == receipt
    with pytest.raises(ValueError, match='scope changed'):
        reuse(Path(job['logical']), dict(job['binding'], captures=[]), job['parents'])


@pytest.mark.parametrize('acquire', [acquire, twelve.acquire])
def test_new_capture_and_restart_charge_once(storage_job, acquire):
    job = storage_job
    assert acquire(job)['status'] == 'completed'
    quota_path = Path(job['budget']) / 'quota.json'
    before = quota_path.read_bytes()
    assert not json.loads(before)['reservations']
    assert verify(job['logical'])['captures'] == len(job['items'])
    assert acquire(job)['status'] == 'reused'
    assert quota_path.read_bytes() == before
