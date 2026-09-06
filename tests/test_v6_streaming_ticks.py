from pathlib import Path

import pytest

from nn_meta import option_tick_dataset as d
from options.data.massive_ticks import TickDataError
from scripts import materialize_v6_tick_store as streaming
from tests.test_option_tick_dataset import evidence, task, capture, request, quote, trade, BASE, SECOND


def bound_task(evidence, requests):
    original = task(evidence, requests)
    source = evidence[0].parent / "streaming-source.txt"
    source.write_bytes(Path(streaming.__file__).read_bytes())
    return d.create_task_manifest(requests,
        selection_reference_paths=[evidence[0], source],
        feature_policy=original["feature_policy"])


def test_streamed_store_matches_existing_materializer_exactly(tmp_path, evidence):
    requests = [request(), request(window_start_ns=BASE + 20*SECOND,
        window_end_ns=BASE+30*SECOND, decision_close_ns=BASE+30*SECOND,
        selected_at_ns=BASE+30*SECOND, raw_spot_available_ns=BASE+30*SECOND)]
    selected = bound_task(evidence, requests)
    first = capture(tmp_path / "first")
    second = capture(tmp_path / "second", start=BASE+20*SECOND, end=BASE+40*SECOND,
                     quotes=[quote(20)], trades=[trade(22)])
    expected = d.materialize_store(selected, [first, second], tmp_path / "old")
    actual = streaming.materialize(selected, [first, second], tmp_path / "streamed")
    assert actual == expected
    loaded = d.load_feature_store(tmp_path / "streamed", expected_task_sha256=selected["task_sha256"],
                                 expected_store_sha256=actual["store_sha256"])
    assert len(loaded) == 2


def test_streamed_store_rejects_ambiguous_coverage_and_unbound_source(tmp_path, evidence):
    first = capture(tmp_path / "first")
    second = capture(tmp_path / "second")
    with pytest.raises(TickDataError, match="source must be bound"):
        streaming.materialize(task(evidence), [first], tmp_path / "unbound")
    with pytest.raises(TickDataError, match="missing or ambiguous"):
        streaming.materialize(bound_task(evidence, [request()]), [first, second], tmp_path / "ambiguous")
    assert not (tmp_path / "ambiguous").exists()


def test_explicit_empty_selection_store_cannot_cover_a_later_decision(tmp_path, evidence):
    import pandas as pd
    original = task(evidence)
    source = tmp_path / "streaming-source.txt"
    source.write_bytes(Path(streaming.__file__).read_bytes())
    selected = d.create_task_manifest([], selection_reference_paths=[evidence[0], source],
        feature_policy=original["feature_policy"], allow_empty=True)
    report = streaming.materialize(selected, [], tmp_path / "empty")
    loaded = d.load_feature_store(tmp_path / "empty", expected_task_sha256=selected["task_sha256"],
        expected_store_sha256=report["store_sha256"])
    assert loaded.empty and selected["empty_selection"] is True
    required = original["requests"][0]
    with pytest.raises(TickDataError, match="required decision window is missing"):
        d.join_decisions(pd.DataFrame([required]), tmp_path / "empty",
            expected_task_sha256=selected["task_sha256"], expected_store_sha256=report["store_sha256"])
