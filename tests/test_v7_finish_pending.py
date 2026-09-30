import pytest
from scripts.finish_v7_pending_20260929 import decision


def test_checkpoint_resumes_and_failure_never_becomes_completion():
    assert decision(dict(status='checkpointed',failed={},securities_replayed=10,securities_required=93))=='continue'
    assert decision(dict(status='failed',failed={'symbol':1}))=='failed'
    assert decision(dict(status='replayed_pending',failed={},securities_replayed=93,securities_required=93))=='complete'
    with pytest.raises(ValueError):
        decision(dict(status='replayed_pending',failed={},securities_replayed=92,securities_required=93))
    with pytest.raises(ValueError):
        decision(dict(status='running',failed={}))
