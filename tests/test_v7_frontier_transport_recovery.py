from copy import deepcopy
import pytest
from scripts.resume_v7_frontier_transport_20261001 import retryable


def stopped():
    return dict(status='draining',active_batches=0,error=None,failed_batches=[
        dict(error_type='TickDataError',reason='Massive ticks HTTP 502') for _ in range(2)])


def test_exact_stopped_transport_failure_is_retryable():
    assert retryable(stopped())


@pytest.mark.parametrize('change',['active','contract','other_failure','other_count'])
def test_other_failures_are_not_implicitly_admitted(change):
    doc=deepcopy(stopped())
    if change=='active':doc['active_batches']=1
    if change=='contract':doc['error']='Snapshot immutable input changed'
    if change=='other_failure':doc['failed_batches'][0]['reason']='HTTP 403'
    if change=='other_count':doc['failed_batches'].append(doc['failed_batches'][0])
    assert not retryable(doc)
