import pytest

from nn_meta.v7.replay_clocks import ReplayClocks
from nn_meta.v7.execution_frontier_v2 import discover_execution
from tests.test_v7_execution_frontier import case


def test_reusable_clocks_preserve_validation_and_share_storage():
    clocks=ReplayClocks([1,2,3,4])
    later=clocks.after(3)
    assert later._values is clocks._values
    assert list(later)==[3,4] and 3 in later and 2 not in later
    assert not clocks.after(5)
    with pytest.raises(AttributeError):later._start=0
    for invalid in [[1,1],[2,1],[1.0]]:
        with pytest.raises(ValueError):ReplayClocks(invalid)


def test_streamed_frontier_exactly_matches_retained_replay(tmp_path):
    from nn_meta.v7.execution_frontier import discover_execution as original
    p,clocks,e,c=case(tmp_path)
    expected=original(p,clocks,e.archive,e.references,e.sessions,select_contract=lambda t:c)
    actual=discover_execution(p,ReplayClocks(clocks),e.archive,e.references,e.sessions,select_contract=lambda t:c)
    assert actual==expected


def test_streamed_frontier_missing_capture_matches_original(tmp_path):
    from nn_meta.v7.execution_frontier import discover_execution as original
    from nn_meta.v7.execution import CaptureUnavailable
    from types import SimpleNamespace
    p,clocks,e,c=case(tmp_path)
    def missing(*args):raise CaptureUnavailable('fixture')
    archive=SimpleNamespace(policy=e.archive.policy,window=missing)
    assert discover_execution(p,ReplayClocks(clocks),archive,e.references,e.sessions,select_contract=lambda t:c)==original(
        p,clocks,archive,e.references,e.sessions,select_contract=lambda t:c)
