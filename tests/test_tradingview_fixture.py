"""Synthetic intake tests only; these files are not TradingView parity evidence."""
from copy import deepcopy
import json

import numpy as np
import pandas as pd
import pytest

from scripts import tradingview_fixture as fixture


@pytest.fixture
def capture(tmp_path):
    index = pd.date_range("2025-01-02 14:30", periods=260, freq="15min", tz="UTC", name="time")
    close = 100 + np.sin(np.arange(260) / 6) * 4 + np.arange(260) * .015
    bars = pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                         "Close": close, "Volume": 1000.}, index=index)
    spec = {"timestamp_column": "time", "timestamp_encoding": "iso8601", "timestamp_semantics": "bar_open",
            "ohlcv_columns": dict(zip(fixture.OHLCV, fixture.OHLCV))}

    def make(script_id="AqRNdhlR"):
        path = tmp_path / f"synthetic-{script_id}.csv"
        bars.to_csv(path, float_format="%.17g")
        metadata = fixture.prepare_template(path, script_id, spec, "America/New_York")
        _, exact, _ = fixture.read_input(path, spec, "America/New_York")
        outputs = fixture._calculator(script_id)(exact, **metadata["parameters"])
        numeric = {"AqRNdhlR": "trend_line", "U7CZ8jtj": "upper_band", "f4N0F439": "basis"}[script_id]
        event = "bull_signal"
        export = bars.copy()
        export["TV Numeric"] = outputs[numeric]
        export["TV Event"] = outputs[event].astype(int)
        export.to_csv(path, float_format="%.17g")
        metadata["input"]["csv_sha256"] = fixture.file_sha256(path)
        metadata["source_verified_against_chart"] = metadata["inputs_verified_against_chart"] = True
        metadata["capture"].update(symbol="SYNTHETIC_TEST_ONLY", exchange="TEST", timeframe="15m",
                                    session="24x7", price_adjustment="raw", minimum_tick=.01,
                                    captured_at=(index[-1] + pd.Timedelta(minutes=15)).isoformat(),
                                    closed_bars_only=True, history_contains_all_calculation_bars=True)
        metadata["columns"] = [
            {"tv_column": "TV Numeric", "python_column": numeric, "kind": "numeric",
             "atol": 1e-12, "rtol": 0, "nan_policy": "match"},
            {"tv_column": "TV Event", "python_column": event, "kind": "event",
             "atol": 0, "rtol": 0, "nan_policy": "forbid", "event_encoding": "zero_one"},
        ]
        return path, metadata, exact, outputs
    return make


def _rewrite(path, metadata, change):
    frame = pd.read_csv(path, keep_default_na=False, dtype=str)
    change(frame)
    frame.to_csv(path, index=False)
    metadata["input"]["csv_sha256"] = fixture.file_sha256(path)


@pytest.mark.parametrize("script_id", list(fixture.ADAPTERS))
def test_all_three_builtin_adapters_and_bound_report(capture, script_id):
    path, metadata, bars, _ = capture(script_id)
    report = fixture.compare_fixture(path, metadata)
    assert report["status"] == "matched" and report["rows"] == len(bars)
    assert report["fixture_identity_sha256"] == metadata["fixture_identity_sha256"]
    assert report["input_ohlcv_sha256"] == metadata["input"]["ohlcv_sha256"]
    assert report["active_pool_admission"] is False and report["origin_authenticated"] is False
    assert report["validator_sha256"] == fixture.file_sha256(fixture.__file__)


@pytest.mark.parametrize("field", ["symbol", "exchange", "timeframe", "timezone", "session",
                                   "price_adjustment", "captured_at", "minimum_tick", "history_start"])
def test_missing_capture_fields_rejected(capture, field):
    path, metadata, *_ = capture()
    del metadata["capture"][field]
    with pytest.raises(fixture.FixtureValidationError):
        fixture.compare_fixture(path, metadata)


@pytest.mark.parametrize("mutation,match", [
    (lambda m: m.update(fixture_identity_sha256="stale"), "stale fixture"),
    (lambda m: m["source"].update(publication_version="999"), "source revision"),
    (lambda m: m.update(source_verified_against_chart=False), "verification"),
    (lambda m: m["capture"].update(closed_bars_only=False), "closed-bar"),
    (lambda m: m["capture"].update(history_contains_all_calculation_bars=False), "closed-bar"),
    (lambda m: m["capture"].update(chart_type="heikin_ashi"), "standard candles"),
    (lambda m: m["capture"].update(captured_at="2025-01-02T00:00:00Z"), "unclosed"),
    (lambda m: m["capture"].update(captured_at="2026-01-02 00:00"), "UTC offset"),
    (lambda m: m["capture"].update(history_start="2025-01-01T00:00:00Z"), "history start"),
    (lambda m: m["input"].update(ohlcv_sha256="wrong"), "OHLCV hash"),
    (lambda m: m["input"].update(timestamp_semantics="bar_close"), "bar-open"),
    (lambda m: m["parameters"].pop("length"), "every calculator parameter"),
])
def test_contract_mutations_fail_closed(capture, mutation, match):
    path, metadata, *_ = capture()
    mutation(metadata)
    with pytest.raises(fixture.FixtureValidationError, match=match):
        fixture.compare_fixture(path, metadata)


def test_duplicate_csv_headers_rejected_before_pandas_can_rename(capture):
    path, metadata, *_ = capture()
    path.write_text(path.read_text().replace("TV Numeric,TV Event", "TV Numeric,TV Numeric", 1))
    metadata["input"]["csv_sha256"] = fixture.file_sha256(path)
    with pytest.raises(fixture.FixtureValidationError, match="duplicates"):
        fixture.compare_fixture(path, metadata)


def test_duplicate_mapping_and_missing_output_rejected(capture):
    path, metadata, *_ = capture()
    metadata["columns"].append(deepcopy(metadata["columns"][0]))
    with pytest.raises(fixture.FixtureValidationError, match="ambiguous"):
        fixture.compare_fixture(path, metadata)
    metadata["columns"].pop()
    metadata["columns"][0]["tv_column"] = "not exported"
    with pytest.raises(fixture.FixtureValidationError, match="missing mapped output"):
        fixture.compare_fixture(path, metadata)


def test_csv_byte_mutation_and_input_price_mutation_rejected(capture):
    path, metadata, *_ = capture()
    path.write_text(path.read_text() + "\n")
    with pytest.raises(fixture.FixtureValidationError, match="CSV hash"):
        fixture.compare_fixture(path, metadata)
    path, metadata, *_ = capture()
    _rewrite(path, metadata, lambda f: f.loc.__setitem__((0, "Volume"), "1001"))
    with pytest.raises(fixture.FixtureValidationError, match="OHLCV hash"):
        fixture.compare_fixture(path, metadata)


def test_numeric_tolerance_and_timestamp_exact_events(capture):
    path, metadata, _, outputs = capture()
    row = int(np.flatnonzero(outputs.bull_signal)[0])
    _rewrite(path, metadata, lambda f: f.loc.__setitem__((0, "TV Numeric"), "100.000001"))
    report = fixture.compare_fixture(path, metadata)
    assert report["status"] == "mismatch" and report["comparison"][0]["mismatch_count"] == 1
    metadata["columns"][0]["atol"] = 1e-5
    assert fixture.compare_fixture(path, metadata)["status"] == "matched"
    def shift_event(frame):
        frame.loc[row, "TV Event"] = "0"
        frame.loc[row + 1, "TV Event"] = "1"
    _rewrite(path, metadata, shift_event)
    report = fixture.compare_fixture(path, metadata)
    assert report["comparison"][1]["mismatch_count"] == 2
    assert len(report["comparison"][1]["first_mismatch_timestamps"]) == 2


def test_nan_policy_matches_locations_never_drops_rows(capture):
    path, metadata, *_ = capture("U7CZ8jtj")
    report = fixture.compare_fixture(path, metadata)
    assert report["comparison"][0]["tv_nan_count"] == 205
    _rewrite(path, metadata, lambda f: f.loc.__setitem__((0, "TV Numeric"), "0"))
    assert fixture.compare_fixture(path, metadata)["comparison"][0]["mismatch_count"] == 1
    metadata["columns"][0]["nan_policy"] = "forbid"
    with pytest.raises(fixture.FixtureValidationError, match="missing value"):
        fixture.compare_fixture(path, metadata)


def test_event_missing_values_require_explicit_one_or_missing_policy(capture):
    path, metadata, *_ = capture()
    _rewrite(path, metadata, lambda f: f.__setitem__("TV Event", f["TV Event"].replace("0", "")))
    with pytest.raises(fixture.FixtureValidationError, match="missing value"):
        fixture.compare_fixture(path, metadata)
    metadata["columns"][1].update(event_encoding="one_or_missing", nan_policy="missing_is_false")
    assert fixture.compare_fixture(path, metadata)["status"] == "matched"
    metadata["columns"][1]["atol"] = .1
    with pytest.raises(fixture.FixtureValidationError, match="zero numerical/time tolerance"):
        fixture.compare_fixture(path, metadata)


def test_precomputed_csv_binds_ohlcv_capture_parameters_and_implementation(capture, tmp_path):
    path, metadata, bars, outputs = capture()
    local = bars.join(outputs)
    local["bull_signal"] = local.bull_signal.astype(int)
    local_path = tmp_path / "synthetic-local.csv"
    local.to_csv(local_path, float_format="%.17g")
    local_metadata = fixture.local_csv_metadata(metadata, local_path, "synthetic test producer")
    report = fixture.compare_fixture(path, metadata, local_csv=local_path, local_metadata=local_metadata)
    assert report["status"] == "matched" and report["local_mode"] == "precomputed_user_declared"
    for key in ("fixture_identity_sha256", "input_ohlcv_sha256", "capture_sha256", "parameters_sha256", "csv_sha256"):
        stale = {**local_metadata, key: "wrong"}
        with pytest.raises(fixture.FixtureValidationError, match="hash mismatch"):
            fixture.compare_fixture(path, metadata, local_csv=local_path, local_metadata=stale)
    local.iloc[0, local.columns.get_loc("Volume")] = 999
    local.to_csv(local_path, float_format="%.17g")
    local_metadata = fixture.local_csv_metadata(metadata, local_path, "synthetic test producer")
    with pytest.raises(fixture.FixtureValidationError, match="exact input OHLCV"):
        fixture.compare_fixture(path, metadata, local_csv=local_path, local_metadata=local_metadata)


def test_template_attestations_stay_unverified(capture):
    path, metadata, *_ = capture()
    template = fixture.prepare_template(path, "AqRNdhlR", metadata["input"], "America/New_York")
    assert template["source_verified_against_chart"] is False
    assert template["capture"]["closed_bars_only"] is False
    assert template["capture"]["symbol"] is None
    assert template["columns"] == []


def test_duplicate_json_keys_and_nonfinite_json_fail(tmp_path):
    path = tmp_path / "metadata.json"
    for text in ('{"symbol":"A","symbol":"B"}', '{"atol":NaN}'):
        path.write_text(text)
        with pytest.raises(fixture.FixtureValidationError):
            fixture.load_metadata(path)


@pytest.mark.parametrize("timestamps", [
    ["2025-11-02 01:30:00"],  # repeated local time at DST fall-back
    ["2025-03-09 02:30:00"],  # nonexistent local time at spring-forward
    ["2025-01-02T14:30:00Z", "2025-01-02T14:30:00Z"],
    ["2025-01-02T14:45:00Z", "2025-01-02T14:30:00Z"],
])
def test_ambiguous_nonexistent_duplicate_or_reversed_times_fail(timestamps):
    with pytest.raises(fixture.FixtureValidationError):
        fixture._timestamps(timestamps, "iso8601", "America/New_York")


@pytest.mark.parametrize("encoding,values", [
    ("iso8601", ["2025-01-02 09:30:00", "2025-01-02 09:45:00"]),
    ("unix_s", ["1735828200", "1735829100"]),
    ("unix_ms", ["1735828200000", "1735829100000"]),
])
def test_explicit_timestamp_encodings_normalize_to_same_instant(encoding, values):
    index = fixture._timestamps(values, encoding, "America/New_York")
    assert index[0] == pd.Timestamp("2025-01-02T14:30:00Z")
    assert index[1] == pd.Timestamp("2025-01-02T14:45:00Z")


def test_all_missing_numeric_comparison_cannot_pass(capture):
    path, metadata, *_ = capture("U7CZ8jtj")
    # Compare just a captured prefix before the first finite band, retaining the
    # whole calculation history for this shorter fixture.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False).iloc[:100]
    frame.to_csv(path, index=False)
    _, _, digest = fixture.read_input(path, metadata["input"], metadata["capture"]["timezone"])
    metadata["input"].update(csv_sha256=fixture.file_sha256(path), ohlcv_sha256=digest)
    with pytest.raises(fixture.FixtureValidationError, match="no finite comparison"):
        fixture.compare_fixture(path, metadata)


def test_cli_writes_report_and_uses_distinct_failure_exit_codes(capture, tmp_path, monkeypatch):
    path, metadata, *_ = capture()
    meta_path, report = tmp_path / "metadata.json", tmp_path / "report.json"
    meta_path.write_text(json.dumps(metadata))
    monkeypatch.setattr("sys.argv", ["fixture", "validate", "--csv", str(path), "--metadata", str(meta_path), "--report", str(report)])
    assert fixture.main() == 0 and json.loads(report.read_text())["status"] == "matched"
    _rewrite(path, metadata, lambda f: f.loc.__setitem__((0, "TV Numeric"), "150"))
    meta_path.write_text(json.dumps(metadata))
    assert fixture.main() == 1 and json.loads(report.read_text())["status"] == "mismatch"
    metadata["fixture_identity_sha256"] = "stale"
    meta_path.write_text(json.dumps(metadata))
    with pytest.raises(SystemExit) as error:
        fixture.main()
    assert error.value.code == 2


def test_numeric_tolerance_cannot_waive_builtin_boolean_events(capture):
    path, metadata, *_ = capture()
    _rewrite(path, metadata, lambda f: f.__setitem__("TV Event", 1 - f["TV Event"].astype(int)))
    metadata["columns"][1].update(kind="numeric", atol=1)
    with pytest.raises(fixture.FixtureValidationError, match="boolean outputs require kind=event"):
        fixture.compare_fixture(path, metadata)


@pytest.mark.parametrize("target", ["external", "local"])
def test_output_only_csv_change_after_parsing_is_rejected(capture, tmp_path, monkeypatch, target):
    path, metadata, bars, outputs = capture()
    local_path = tmp_path / "synthetic-local.csv"
    local = bars.join(outputs)
    local["bull_signal"] = local.bull_signal.astype(int)
    local.to_csv(local_path, float_format="%.17g")
    local_metadata = fixture.local_csv_metadata(metadata, local_path, "synthetic producer")
    original = fixture._local_outputs
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        changed = path if target == "external" else local_path
        frame = pd.read_csv(changed, dtype=str, keep_default_na=False)
        column = "TV Numeric" if target == "external" else "trend_line"
        frame.loc[0, column] = "999"
        frame.to_csv(changed, index=False)
        return result
    monkeypatch.setattr(fixture, "_local_outputs", mutate)
    with pytest.raises(fixture.FixtureValidationError, match="CSV changed during comparison"):
        fixture.compare_fixture(path, metadata, local_csv=local_path, local_metadata=local_metadata)


@pytest.mark.parametrize("changed", ["runtime", "validator"])
def test_runtime_or_validator_change_during_comparison_rejected(capture, monkeypatch, changed):
    path, metadata, *_ = capture()
    original_outputs, original_entry, original_hash = fixture._local_outputs, fixture._entry, fixture.file_sha256
    def mutate(*args, **kwargs):
        result = original_outputs(*args, **kwargs)
        if changed == "runtime":
            monkeypatch.setattr(fixture, "_entry", lambda script: {**original_entry(script), "fixture_identity_sha256": "changed"})
        else:
            monkeypatch.setattr(fixture, "file_sha256", lambda p: "changed" if str(p) == fixture.__file__ else original_hash(p))
        return result
    monkeypatch.setattr(fixture, "_local_outputs", mutate)
    with pytest.raises(fixture.FixtureValidationError, match="changed during comparison"):
        fixture.compare_fixture(path, metadata)


@pytest.mark.parametrize("victim", ["csv", "metadata", "local_csv", "local_metadata"])
@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_report_cannot_overwrite_any_intake_file(capture, tmp_path, monkeypatch, victim, alias):
    path, metadata, *_ = capture()
    inputs = {"csv": path, "metadata": tmp_path / "metadata.json",
              "local_csv": tmp_path / "local.csv", "local_metadata": tmp_path / "local.json"}
    inputs["metadata"].write_text(json.dumps(metadata))
    inputs["local_csv"].write_text("local evidence")
    inputs["local_metadata"].write_text("local metadata")
    target = inputs[victim]
    if alias != "same":
        target = tmp_path / "report-alias.json"
        if alias == "symlink":
            target.symlink_to(inputs[victim])
        else:
            target.hardlink_to(inputs[victim])
    before = {name: p.read_bytes() for name, p in inputs.items()}
    args = ["fixture", "validate", "--report", str(target)]
    for name, p in inputs.items():
        args.extend(["--" + name.replace("_", "-"), str(p)])
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(SystemExit) as error:
        fixture.main()
    assert error.value.code == 2
    assert before == {name: p.read_bytes() for name, p in inputs.items()}


def test_report_records_actual_calculation_environment(capture):
    path, metadata, *_ = capture()
    report = fixture.compare_fixture(path, metadata)
    assert report["calculation_environment"] == {
        "python": fixture.platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
