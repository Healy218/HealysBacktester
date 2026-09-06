"""Synthetic integrity tests; never actual TradingView execution evidence."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import tradingview_fixture as fixture


@pytest.fixture
def instrumented(tmp_path):
    def make(script_id="AqRNdhlR"):
        index = pd.date_range("2025-01-02", periods=260, freq="15min", tz="UTC", name="time")
        close = 100 + np.sin(np.arange(260) / 6) * 4
        bars = pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                             "Close": close, "Volume": 1000.}, index=index)
        csv = tmp_path / f"synthetic-{script_id}.csv"
        bars.to_csv(csv, float_format="%.17g")
        spec = {"timestamp_column": "time", "timestamp_encoding": "iso8601",
                "timestamp_semantics": "bar_open", "ohlcv_columns": dict(zip(fixture.OHLCV, fixture.OHLCV))}
        metadata = fixture.prepare_template(csv, script_id, spec, "UTC")
        _, exact, _ = fixture.read_input(csv, spec, "UTC")
        outputs = fixture._calculator(script_id)(exact, **metadata["parameters"])
        numerical, expression, event = {
            "AqRNdhlR": ("trend_line", "trend_line", "turned_bull"),
            "U7CZ8jtj": ("midline", "v", "bullFibCross"),
            "f4N0F439": ("basis", "basis", "upSignal"),
        }[script_id]
        export = exact.copy()
        export["CSV Numeric"] = outputs[numerical]
        export["CSV Event"] = outputs.bull_signal.astype(int)
        export.to_csv(csv, float_format="%.17g")
        metadata["input"]["csv_sha256"] = fixture.file_sha256(csv)
        metadata.update(schema_version=2, source_verified_against_chart=False, inputs_verified_against_chart=True)
        metadata["capture"].update(symbol="SYNTHETIC", exchange="TEST", timeframe="15m", session="24x7",
            price_adjustment="raw", minimum_tick=.01, closed_bars_only=True,
            history_contains_all_calculation_bars=True, captured_at=(index[-1] + pd.Timedelta(minutes=15)).isoformat())
        plots = [
            {"title": "TVF:numeric", "expression": expression, "python_column": numerical, "kind": "numeric"},
            {"title": "TVF:event", "expression": event + " ? 1 : 0", "python_column": "bull_signal", "kind": "event"},
        ]
        source = tmp_path / f"synthetic-{script_id}.pine"
        entry = fixture._entry(script_id)
        source.write_bytes((fixture.ROOT / entry["source"]["path"]).read_bytes() + fixture.instrumentation_append(plots))
        receipt = fixture.prepare_instrumentation_receipt(script_id, source, plots)
        receipt["review"].update(reviewed=True, reviewer="SYNTHETIC TEST ONLY", reviewed_at="2026-09-06T00:00:00Z",
                                 reviewed_diff_sha256=receipt["diff_sha256"], observation_semantics_verified=True)
        receipt["compiled_on_tradingview"] = True  # synthetic attestation only
        metadata["source_capture"] = {"kind": "reviewed_append_only_plots", "receipt_sha256": fixture.hash_json(receipt),
                                      "instrumented_source_verified_against_chart": True}
        metadata["columns"] = [
            {"tv_column": "CSV Numeric", "instrumented_plot_title": "TVF:numeric", "python_column": numerical,
             "kind": "numeric", "atol": 1e-12, "rtol": 0, "nan_policy": "match"},
            {"tv_column": "CSV Event", "instrumented_plot_title": "TVF:event", "python_column": "bull_signal",
             "kind": "event", "atol": 0, "rtol": 0, "nan_policy": "forbid", "event_encoding": "zero_one"},
        ]
        return csv, metadata, source, receipt, exact, outputs
    return make


def compare(case):
    csv, metadata, source, receipt, *_ = case
    return fixture.compare_fixture(csv, metadata, instrumented_source=source, instrumentation_manifest=receipt)


def snapshot(metadata, bars, mode="fresh_load", start=-1):
    index = bars.index
    sequence = index[start:]
    metadata["comparison_scope"] = {
        "kind": "terminal_snapshot", "terminal_bar_open": index[-1].isoformat(),
        "execution": {"mode": mode, "history_origin": index[0].isoformat(), "sequence_verified": True,
                      "steps": [{"action": "load" if i == 0 else "forward", "terminal_bar_open": stamp.isoformat()}
                                for i, stamp in enumerate(sequence)]},
    }


@pytest.mark.parametrize("script_id", list(fixture.ADAPTERS))
def test_exact_append_three_adapters_keep_distinct_source_identity(instrumented, script_id):
    case = instrumented(script_id)
    report = compare(case)
    assert report["status"] == "matched" and report["compared_rows"] == 260
    assert report["instrumentation"]["executed_source_sha256"] != report["source"]["sha256"]
    assert report["fixture_identity_sha256"] == case[1]["fixture_identity_sha256"]
    assert report["instrumentation"]["review_authenticated"] is False
    assert report["origin_authenticated"] is False and report["active_pool_admission"] is False


@pytest.mark.parametrize("mutation", [
    lambda r: r["review"].update(reviewed=False),
    lambda r: r["review"].update(observation_semantics_verified=False),
    lambda r: r["review"].update(reviewed_diff_sha256="wrong"),
    lambda r: r["review"].update(reviewed_at="2026-09-06"),
    lambda r: r.update(compiled_on_tradingview=False),
    lambda r: r.update(instrumented_sha256="wrong"),
    lambda r: r["original_source"].update(publication_version="999"),
    lambda r: r.update(diff="relabelled"),
    lambda r: r.update(model_admission=True),
])
def test_unreviewed_or_relabelled_receipts_fail(instrumented, mutation):
    case = instrumented()
    mutation(case[3])
    case[1]["source_capture"]["receipt_sha256"] = fixture.hash_json(case[3])
    with pytest.raises(fixture.FixtureValidationError):
        compare(case)


@pytest.mark.parametrize("prefix_change", [b"//@version=6\n", b"// replace license\n", b"length = 1\n"])
def test_header_license_or_algorithm_prefix_edits_rejected(instrumented, prefix_change):
    case = instrumented()
    case[2].write_bytes(prefix_change + case[2].read_bytes())
    with pytest.raises(fixture.FixtureValidationError, match="exact original"):
        compare(case)


@pytest.mark.parametrize("expression", ["request.security(\"X\", \"D\", close)", "f_mutating()", "close * 2", "x := 1", "close)\nx = 1\nplot(close"])
def test_arbitrary_new_computation_not_allowed(expression):
    with pytest.raises(fixture.FixtureValidationError):
        fixture.instrumentation_append([{"title": "TVF:x", "expression": expression, "kind": "numeric", "python_column": "x"}])


def test_exact_context_helpers_are_observations_only():
    plots = [{"title": "TVF:atr", "expression": "ta.atr(14)", "kind": "numeric", "python_column": None},
             {"title": "TVF:vwap", "expression": "ta.vwap(hlc3)", "kind": "numeric", "python_column": None},
             {"title": "TVF:2D", "expression": 'timeframe.change("2D") ? 1 : 0', "kind": "event", "python_column": None}]
    assert fixture.instrumentation_append(plots).count(b"plot(") == 3


@pytest.mark.parametrize("change", [
    lambda m: m.update(source_verified_against_chart=True),
    lambda m: m.update(schema_version=1),
    lambda m: m.update(source_capture={"kind": "unmodified_publication"}),
    lambda m: m["source_capture"].update(receipt_sha256="stale"),
    lambda m: m["columns"][1].update(kind="numeric", atol=1),
    lambda m: m["columns"][0].update(python_column="direction"),
    lambda m: m["columns"][0].update(instrumented_plot_title="TVF:unknown"),
])
def test_capture_relabel_and_mapping_reinterpretation_rejected(instrumented, change):
    case = instrumented()
    change(case[1])
    with pytest.raises(fixture.FixtureValidationError):
        compare(case)


def test_terminal_mask_uses_full_history_and_reports_exact_scope(instrumented, monkeypatch):
    case = instrumented()
    csv, metadata, _, _, bars, _ = case
    snapshot(metadata, bars)
    frame = pd.read_csv(csv, dtype=str, keep_default_na=False)
    frame.loc[:258, "CSV Numeric"] = -999
    frame.loc[:258, "CSV Event"] = ""  # source did not execute those historical plot values
    frame.to_csv(csv, index=False, float_format="%.17g")
    metadata["input"]["csv_sha256"] = fixture.file_sha256(csv)
    original = fixture._local_outputs
    def check_history(m, b, *args):
        assert len(b) == 260 and b.index[0] == bars.index[0]
        return original(m, b, *args)
    monkeypatch.setattr(fixture, "_local_outputs", check_history)
    report = compare(case)
    assert report["status"] == "matched" and report["rows"] == 260 and report["compared_rows"] == 1
    assert report["compared_bar_opens"] == [bars.index[-1].isoformat()]
    frame.loc[259, "CSV Numeric"] = -999
    frame.to_csv(csv, index=False, float_format="%.17g")
    metadata["input"]["csv_sha256"] = fixture.file_sha256(csv)
    report = compare(case)
    assert report["status"] == "mismatch"
    assert report["comparison"][0]["first_mismatch_timestamps"] == [bars.index[-1].isoformat()]


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(terminal_bar_open="2025-01-01T00:00:00Z"),
    lambda s: s["execution"].update(sequence_verified=False),
    lambda s: s["execution"].update(history_origin="2025-01-01T00:00:00Z"),
    lambda s: s["execution"]["steps"].pop(1),
    lambda s: s["execution"]["steps"][1].update(action="jump"),
    lambda s: s["execution"].update(mode="fresh_load"),
])
def test_replay_sequence_cannot_skip_history_or_relabel_execution(instrumented, mutation):
    case = instrumented()
    snapshot(case[1], case[4], mode="continuous_replay", start=-4)
    assert compare(case)["status"] == "matched"
    mutation(case[1]["comparison_scope"])
    with pytest.raises(fixture.FixtureValidationError):
        compare(case)


def test_precomputed_binding_includes_instrumentation_and_snapshot_scope(instrumented, tmp_path):
    case = instrumented()
    csv, metadata, source, receipt, bars, output = case
    snapshot(metadata, bars)
    local = bars.join(output)
    local.bull_signal = local.bull_signal.astype(int)
    local_csv = tmp_path / "python.csv"
    local.to_csv(local_csv, float_format="%.17g")
    binding = fixture.local_csv_metadata(metadata, local_csv, "synthetic test")
    args = dict(local_csv=local_csv, local_metadata=binding, instrumented_source=source, instrumentation_manifest=receipt)
    assert fixture.compare_fixture(csv, metadata, **args)["status"] == "matched"
    metadata["comparison_scope"] = {"kind": "full_series"}
    with pytest.raises(fixture.FixtureValidationError, match="local CSV identity"):
        fixture.compare_fixture(csv, metadata, **args)


def test_instrumented_source_race_detected(instrumented, monkeypatch):
    case = instrumented()
    original = fixture._local_outputs
    def mutate(*args):
        result = original(*args)
        case[2].write_bytes(case[2].read_bytes() + b"// changed\n")
        return result
    monkeypatch.setattr(fixture, "_local_outputs", mutate)
    with pytest.raises(fixture.FixtureValidationError, match="instrumented source changed"):
        compare(case)


def test_report_cannot_replace_instrumented_source_or_receipt(instrumented, tmp_path):
    case = instrumented()
    source = case[2]
    alias = tmp_path / "source-alias.pine"
    alias.hardlink_to(source)
    with pytest.raises(fixture.FixtureValidationError, match="aliases"):
        fixture._report_destination(alias, [source])


@pytest.fixture
def unavailable_case(instrumented):
    case = instrumented("U7CZ8jtj")
    csv, metadata, source, receipt, bars, outputs = case
    frame = pd.read_csv(csv, dtype=str, keep_default_na=False).iloc[:200].copy()
    frame["CSV Numeric"] = ""
    frame.to_csv(csv, index=False)
    _, prefix, digest = fixture.read_input(csv, metadata["input"], "UTC")
    metadata["input"].update(csv_sha256=fixture.file_sha256(csv), ohlcv_sha256=digest)
    metadata["capture"]["captured_at"] = (prefix.index[-1] + pd.Timedelta(minutes=15)).isoformat()
    metadata["columns"][0].update(python_column="upper_band")
    plots = deepcopy(receipt["plots"])
    plots[0].update(python_column="upper_band", expression="b1")
    entry = fixture._entry("U7CZ8jtj")
    source.write_bytes((fixture.ROOT / entry["source"]["path"]).read_bytes() + fixture.instrumentation_append(plots))
    revised = fixture.prepare_instrumentation_receipt("U7CZ8jtj", source, plots)
    revised.update(compiled_on_tradingview=True)
    revised["review"].update(receipt["review"], reviewed_diff_sha256=revised["diff_sha256"])
    metadata["source_capture"]["receipt_sha256"] = fixture.hash_json(revised)
    return csv, metadata, source, revised, prefix, outputs.iloc[:200]


def test_unavailable_is_opt_in_and_never_finite_parity(unavailable_case):
    case = unavailable_case
    with pytest.raises(fixture.FixtureValidationError, match="no finite"):
        compare(case)
    case[1]["columns"][0].update(expectation="unavailable", atol=0)
    report = compare(case)
    assert report["status"] == "matched_with_unavailable"
    assert report["unavailable_columns"] == ["upper_band"]
    result = report["comparison"][0]
    assert result["status"] == "matched_unavailable" and result["evidence_kind"] == "missingness_only"
    assert result["finite_pair_count"] == 0 and result["max_absolute_error"] is None
    assert result["tv_nan_count"] == result["python_nan_count"] == 200
    case[1]["columns"] = case[1]["columns"][:1]
    assert compare(case)["status"] == "matched_unavailable"


def test_unavailable_terminal_preserves_complete_warmup_history(unavailable_case):
    case = unavailable_case
    case[1]["columns"][0].update(expectation="unavailable", atol=0)
    case[1]["columns"] = case[1]["columns"][:1]
    snapshot(case[1], case[4])
    report = compare(case)
    assert report["status"] == "matched_unavailable"
    assert report["rows"] == 200 and report["compared_rows"] == 1
    assert report["input_ohlcv_sha256"] == case[1]["input"]["ohlcv_sha256"]
    assert report["comparison"][0]["python_nan_count"] == 1


@pytest.mark.parametrize("side", ["tv", "python", "both"])
def test_unavailable_rejects_any_finite_or_one_sided_missing_value(unavailable_case, monkeypatch, side):
    case = unavailable_case
    case[1]["columns"][0].update(expectation="unavailable", atol=0)
    if side in ("tv", "both"):
        frame = pd.read_csv(case[0], dtype=str, keep_default_na=False)
        frame.loc[199, "CSV Numeric"] = "0"
        frame.to_csv(case[0], index=False)
        case[1]["input"]["csv_sha256"] = fixture.file_sha256(case[0])
    if side in ("python", "both"):
        original = fixture._local_outputs
        def finite(*args):
            output, mode = original(*args)
            output.loc[output.index[-1], "upper_band"] = 0.
            return output, mode
        monkeypatch.setattr(fixture, "_local_outputs", finite)
    with pytest.raises(fixture.FixtureValidationError, match="every selected value missing"):
        compare(case)


@pytest.mark.parametrize("mutation", [
    lambda m: m["columns"][0].update(atol=1),
    lambda m: m["columns"][0].update(rtol=.1),
    lambda m: m["columns"][0].update(nan_policy="forbid"),
    lambda m: m["columns"][0].update(expectation="anything"),
    lambda m: m["columns"][1].update(expectation="unavailable"),
])
def test_unavailable_cannot_waive_events_tolerances_or_nan_policy(unavailable_case, mutation):
    case = unavailable_case
    case[1]["columns"][0].update(expectation="unavailable", atol=0)
    mutation(case[1])
    with pytest.raises(fixture.FixtureValidationError):
        compare(case)
