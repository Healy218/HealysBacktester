"""The streamed fast path must not turn partial minutes into closed bars."""
import pandas as pd
import pytest

from nn_meta.live.feeds.barstore import BarStore, aggregate_15m


def minutes(n=15):
    index = pd.date_range("2026-09-04 13:30", periods=n, freq="1min")
    return pd.DataFrame({"Open": range(n), "High": [i + 2 for i in range(n)],
                         "Low": [i - 1 for i in range(n)],
                         "Close": [i + 1 for i in range(n)], "Volume": 10}, index=index)


@pytest.mark.parametrize("kind", ["single", "missing", "duplicate", "seconds"])
def test_elapsed_bucket_requires_exact_minute_coverage(kind):
    frame = minutes()
    if kind == "single":
        frame = frame.iloc[-1:]
    elif kind == "missing":
        frame = frame.drop(frame.index[7])
    elif kind == "duplicate":
        frame = pd.concat([frame.iloc[:-1], frame.iloc[:1]])
    else:
        index = frame.index.to_list()
        index[7] += pd.Timedelta(seconds=1)
        frame.index = pd.DatetimeIndex(index)
    with pytest.raises(ValueError, match="15 distinct minute-aligned"):
        aggregate_15m(frame, now=pd.Timestamp("2026-09-04 13:45"))


def test_forming_bucket_dropped_before_validation():
    frame = minutes(16)
    frame.index = frame.index[:-1].append(pd.DatetimeIndex(["2026-09-04 13:45:01"]))
    result = aggregate_15m(frame, now=pd.Timestamp("2026-09-04 13:46", tz="UTC"))
    assert list(result.index) == [pd.Timestamp("2026-09-04 13:30")]
    with pytest.raises(ValueError):
        aggregate_15m(frame, now=pd.Timestamp("2026-09-04 14:00"))


def test_no_now_uses_last_observed_minute_end():
    result = aggregate_15m(minutes(16))
    assert len(result) == 1


def test_complete_unsorted_bucket_aggregates_chronologically():
    result = aggregate_15m(minutes().iloc[::-1], now=pd.Timestamp("2026-09-04 13:45"))
    assert result.iloc[0].to_dict() == {"Open": 0., "High": 16., "Low": -1.,
                                        "Close": 15., "Volume": 150.}


def test_store_propagates_partial_bucket_error(tmp_path):
    store = BarStore(tmp_path)
    store.append_1m("TEST", [{"timestamp": "2026-09-04 13:44", "open": 1,
                               "high": 1, "low": 1, "close": 1, "volume": 1}])
    with pytest.raises(ValueError, match="streamed 15m bucket"):
        store.read_15m("TEST", now=pd.Timestamp("2026-09-04 13:45"))
