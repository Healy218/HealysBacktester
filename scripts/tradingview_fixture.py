"""Intake and compare user-captured TradingView fixtures; never admit a strategy.

CSV provenance and chart settings are explicit user attestations, not an
authentication mechanism. See docs/specs/TRADINGVIEW_FIXTURE_RUNBOOK.md.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import hashlib
import inspect
import io
import json
import os
import platform
import re
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from indicators.tradingview_registry import ROOT, build_catalog

OHLCV = ("Open", "High", "Low", "Close", "Volume")
ADAPTERS = {
    "AqRNdhlR": ("v3.tv_gaussian", "gaussian_filter_trend"),
    "U7CZ8jtj": ("v3.tv_fibonacci", "fibonacci_trend_continuation"),
    "f4N0F439": ("v3.tv_uptrick", "uptrick_adaptive_trend"),
}


class FixtureValidationError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise FixtureValidationError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_metadata(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, f"duplicate metadata key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise FixtureValidationError(f"nonfinite JSON value: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=invalid)


def _read_csv(path):
    payload = Path(path).read_bytes()
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True))
    _require(len(rows) > 1, "CSV must contain headers and data")
    headers = rows[0]
    _require(all(_text(h) for h in headers) and len(set(headers)) == len(headers),
             "CSV headers are blank or ambiguous duplicates")
    _require(all(len(row) == len(headers) for row in rows[1:]), "CSV has ragged/blank rows")
    frame = pd.DataFrame(rows[1:], columns=headers)
    frame.attrs["csv_sha256"] = hashlib.sha256(payload).hexdigest()
    return frame


def _timestamps(values, encoding, timezone):
    _require(encoding in ("iso8601", "unix_s", "unix_ms"), "unsupported timestamp encoding")
    ZoneInfo(timezone)
    result = []
    for value in values:
        try:
            if encoding.startswith("unix_"):
                _require(bool(re.fullmatch(r"-?\d+", value)), "epoch timestamps must be integers")
                stamp = pd.Timestamp(int(value), unit=encoding[5:], tz="UTC")
            else:
                _require(not re.fullmatch(r"[\d.]+", value or ""), "ISO timestamp cannot be a bare number")
                stamp = pd.Timestamp(value)
                _require(not pd.isna(stamp), "missing timestamp")
                if stamp.tzinfo is None:
                    stamp = stamp.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
                stamp = stamp.tz_convert("UTC")
        except Exception as error:
            # pandas timezone backends use distinct DST exception classes.
            raise FixtureValidationError(f"invalid/ambiguous timestamp {value!r}: {error}") from error
        result.append(stamp)
    index = pd.DatetimeIndex(result, name="time")
    _require(index.is_unique and index.is_monotonic_increasing, "timestamps must be unique and increasing")
    return index


def _numbers(values, name, missing=False):
    parsed = []
    for value in values:
        if isinstance(value, str) and value.strip().lower() in ("", "nan", "na"):
            _require(missing, f"missing value in {name}")
            parsed.append(np.nan)
        else:
            try:
                number = float(value)
            except (TypeError, ValueError) as error:
                raise FixtureValidationError(f"nonnumeric value in {name}: {value!r}") from error
            _require(np.isfinite(number) or (missing and np.isnan(number)), f"nonfinite value in {name}")
            parsed.append(number)
    return np.asarray(parsed, dtype=float)


def read_input(csv_path, spec, timezone):
    _require(isinstance(spec, dict), "input specification must be an object")
    frame = _read_csv(csv_path)
    column_map = spec.get("ohlcv_columns", {})
    _require(isinstance(column_map, dict), "OHLCV mapping must be an object")
    _require(set(column_map) == set(OHLCV), "declare all five OHLCV column mappings")
    names = [spec.get("timestamp_column"), *column_map.values()]
    _require(all(_text(name) for name in names) and len(set(names)) == 6,
             "timestamp/OHLCV mappings must be distinct explicit columns")
    _require(all(name in frame for name in names), "missing mapped timestamp/OHLCV column")
    _require(spec.get("timestamp_semantics") == "bar_open", "only bar-open timestamps are supported")
    index = _timestamps(frame[names[0]], spec.get("timestamp_encoding"), timezone)
    bars = pd.DataFrame({key: _numbers(frame[column_map[key]], key) for key in OHLCV}, index=index)
    _require((bars.Volume >= 0).all(), "negative volume")
    _require(((bars.High >= bars[["Open", "Close", "Low"]].max(axis=1)) &
              (bars.Low <= bars[["Open", "Close", "High"]].min(axis=1))).all(), "invalid OHLC range")
    # Stable binary schema: UTC ns, then row-major float64 OHLCV in named order.
    digest = hashlib.sha256(b"tradingview-fixture-ohlcv-v1\0")
    digest.update(index.as_unit("ns").asi8.astype("<i8").tobytes())
    digest.update(bars.loc[:, list(OHLCV)].to_numpy(dtype="<f8").tobytes())
    frame.index = index
    return frame, bars, digest.hexdigest()


def _entry(script_id):
    entries = [row for row in build_catalog()["scripts"] if row["script_id"] == script_id]
    _require(len(entries) == 1 and "fixture_identity_sha256" in entries[0], "unknown or unimplemented script")
    return entries[0]


def _calculator(script_id):
    import importlib
    _require(script_id in ADAPTERS, "no built-in fixture calculator; supply a bound local CSV")
    module, function = ADAPTERS[script_id]
    return getattr(importlib.import_module(module), function)


def prepare_template(csv_path, script_id, input_spec, timezone):
    """Populate verifiable identities only; capture attestations remain unset."""
    frame, bars, digest = read_input(csv_path, input_spec, timezone)
    entry = _entry(script_id)
    defaults = {}
    if script_id in ADAPTERS:
        defaults = {key: value.default for key, value in
                    inspect.signature(_calculator(script_id)).parameters.items() if key != "bars"}
    return {
        "schema_version": 1, "script_id": script_id,
        "fixture_identity_sha256": entry["fixture_identity_sha256"],
        "source": {key: entry["source"][key] for key in ("pine_id", "publication_version", "sha256")},
        "source_verified_against_chart": False, "inputs_verified_against_chart": False,
        "capture": {"provider": "TradingView", "symbol": None, "exchange": None,
                    "timeframe": None, "timezone": timezone, "session": None,
                    "price_adjustment": None, "chart_type": "standard", "minimum_tick": None,
                    "captured_at": None, "closed_bars_only": False,
                    "history_contains_all_calculation_bars": False,
                    "history_start": bars.index[0].isoformat()},
        "input": {**input_spec, "csv_sha256": frame.attrs["csv_sha256"], "ohlcv_sha256": digest},
        "parameters": defaults, "columns": [], "available_csv_columns": list(frame.columns),
    }


def _validate_intake(csv_path, metadata):
    _require(isinstance(metadata, dict), "metadata must be an object")
    _require(metadata.get("schema_version") == 1, "unsupported metadata schema")
    entry = _entry(metadata.get("script_id"))
    _require(metadata.get("fixture_identity_sha256") == entry["fixture_identity_sha256"],
             "stale fixture identity: recapture/review changed source or runtime")
    _require(metadata.get("source") == {key: entry["source"][key] for key in
                                        ("pine_id", "publication_version", "sha256")}, "source revision mismatch")
    _require(metadata.get("source_verified_against_chart") is True and
             metadata.get("inputs_verified_against_chart") is True, "chart source/input verification is required")
    capture = metadata.get("capture", {})
    _require(isinstance(capture, dict), "capture must be an object")
    _require(all(_text(capture.get(key)) for key in ("symbol", "exchange", "timeframe", "timezone",
                                                   "session", "price_adjustment", "captured_at", "history_start")),
             "missing explicit chart capture metadata")
    _require(capture.get("provider") == "TradingView" and capture.get("chart_type") == "standard",
             "only TradingView standard candles are supported")
    _require(capture["price_adjustment"] in ("raw", "splits", "splits_dividends"), "unknown price adjustment")
    _require(capture.get("closed_bars_only") is True and
             capture.get("history_contains_all_calculation_bars") is True, "complete closed-bar history attestation required")
    tick = capture.get("minimum_tick")
    _require(isinstance(tick, (int, float)) and not isinstance(tick, bool) and np.isfinite(tick) and tick > 0,
             "positive instrument minimum_tick required")
    timeframe = re.fullmatch(r"([1-9]\d*)(s|m|h)", capture["timeframe"])
    _require(timeframe is not None, "use an explicit fixed intraday timeframe such as 15m")
    seconds = int(timeframe[1]) * {"s": 1, "m": 60, "h": 3600}[timeframe[2]]
    _require(seconds <= 86400, "timeframe exceeds fixed intraday scope")
    spec = metadata.get("input", {})
    _require(isinstance(spec, dict), "input specification must be an object")
    _require(spec.get("csv_sha256") == file_sha256(csv_path), "TradingView CSV hash mismatch")
    frame, bars, digest = read_input(csv_path, spec, capture["timezone"])
    _require(frame.attrs["csv_sha256"] == spec["csv_sha256"], "TradingView CSV changed during intake")
    _require(spec.get("ohlcv_sha256") == digest, "OHLCV hash mismatch")
    captured_at = pd.Timestamp(capture["captured_at"])
    _require(not pd.isna(captured_at) and captured_at.tzinfo is not None, "captured_at must include UTC offset")
    _require(captured_at >= bars.index[-1] + pd.Timedelta(seconds=seconds), "capture includes an unclosed bar")
    start = pd.Timestamp(capture["history_start"])
    _require(start.tzinfo is not None and start == bars.index[0], "calculation history start differs from export")
    gaps = np.diff(bars.index.as_unit("ns").asi8)
    _require((gaps % (seconds * 1_000_000_000) == 0).all(), "timestamps do not match declared timeframe spacing")
    _require(isinstance(metadata.get("parameters"), dict), "explicit parameter object required")
    hash_json(metadata["parameters"])
    if metadata["script_id"] in ADAPTERS:
        expected = set(inspect.signature(_calculator(metadata["script_id"])).parameters) - {"bars"}
        _require(set(metadata["parameters"]) == expected, "capture every calculator parameter explicitly")
    if metadata["script_id"] == "f4N0F439":
        _require(metadata["parameters"]["minimum_tick"] == capture["minimum_tick"],
                 "Uptrick minimum_tick differs from instrument capture")
    return entry, frame, bars, digest


def local_csv_metadata(metadata, csv_path, producer):
    """Bind a caller-produced canonical local CSV; this does not authenticate it."""
    _require(_text(producer), "identify the local calculation producer")
    return {"schema_version": 1, "producer": producer, "csv_sha256": file_sha256(csv_path),
            "fixture_identity_sha256": metadata["fixture_identity_sha256"],
            "input_ohlcv_sha256": metadata["input"]["ohlcv_sha256"],
            "capture_sha256": hash_json(metadata["capture"]),
            "parameters_sha256": hash_json(metadata["parameters"])}


def _local_outputs(metadata, bars, digest, csv_path, local_metadata):
    if csv_path is None:
        _require(local_metadata is None, "local metadata requires a local CSV")
        calculator = _calculator(metadata["script_id"])
        return calculator(bars, **metadata["parameters"]), "built_in"
    _require(isinstance(local_metadata, dict), "bound local CSV metadata required")
    producer = local_metadata.get("producer")
    expected = local_csv_metadata(metadata, csv_path, producer)
    _require(local_metadata == expected, "local CSV identity/input/parameter/capture hash mismatch")
    spec = {"timestamp_column": "time", "timestamp_encoding": "iso8601", "timestamp_semantics": "bar_open",
            "ohlcv_columns": dict(zip(OHLCV, OHLCV))}
    local, local_bars, local_hash = read_input(csv_path, spec, "UTC")
    _require(local.attrs["csv_sha256"] == local_metadata["csv_sha256"], "local CSV changed during intake")
    _require(local_hash == digest and local_bars.index.equals(bars.index), "local CSV does not contain the exact input OHLCV")
    return local, "precomputed_user_declared"


def _events(values, name, encoding):
    numbers = _numbers(values, name, missing=encoding == "one_or_missing")
    if encoding == "one_or_missing":
        _require((np.isnan(numbers) | (numbers == 1)).all(), f"{name}: expected one or missing event encoding")
        return numbers == 1
    _require(encoding == "zero_one" and np.isin(numbers, [0, 1]).all(), f"{name}: expected exact zero/one events")
    return numbers == 1


def compare_fixture(csv_path, metadata, *, local_csv=None, local_metadata=None):
    metadata, local_metadata = deepcopy(metadata), deepcopy(local_metadata)
    validator_hash = file_sha256(__file__)
    entry, external, bars, digest = _validate_intake(csv_path, metadata)
    local, mode = _local_outputs(metadata, bars, digest, local_csv, local_metadata)
    _require(local.index.equals(bars.index), "local output timestamps differ from input")
    mappings = metadata.get("columns")
    _require(isinstance(mappings, list) and len(mappings) > 0, "declare at least one output column")
    _require(all(isinstance(item, dict) for item in mappings), "each output mapping must be an object")
    for key in ("tv_column", "python_column"):
        names = [item.get(key) for item in mappings]
        _require(all(_text(name) for name in names) and len(set(names)) == len(names), "ambiguous output column mapping")
    results = []
    for mapping in mappings:
        tv, py = mapping["tv_column"], mapping["python_column"]
        _require(tv in external and py in local, f"missing mapped output: {tv} / {py}")
        _require(tv not in [metadata["input"]["timestamp_column"], *metadata["input"]["ohlcv_columns"].values()]
                 and py not in ["time", *OHLCV], "output mappings cannot compare input columns")
        kind, policy = mapping.get("kind"), mapping.get("nan_policy")
        if mode == "built_in" and pd.api.types.is_bool_dtype(local[py].dtype):
            _require(kind == "event", f"{py}: built-in boolean outputs require kind=event")
        atol, rtol = mapping.get("atol"), mapping.get("rtol")
        _require(all(isinstance(v, (float, int)) and not isinstance(v, bool) and np.isfinite(v) and v >= 0
                     for v in (atol, rtol)), "declare finite nonnegative absolute/relative tolerances")
        if kind == "event":
            encoding = mapping.get("event_encoding")
            _require(atol == rtol == 0, "event comparison has zero numerical/time tolerance")
            _require((encoding, policy) in (("zero_one", "forbid"), ("one_or_missing", "missing_is_false")),
                     "declare event encoding and matching missing-value policy")
            expected = _events(external[tv], tv, encoding)
            actual = _events(local[py], py, "zero_one")
            matched = expected == actual
            details = {"tv_true_count": int(expected.sum()), "python_true_count": int(actual.sum())}
        else:
            _require(kind == "numeric" and policy in ("match", "forbid"), "unsupported kind/NaN policy")
            expected = _numbers(external[tv], tv, missing=policy == "match")
            actual = _numbers(local[py], py, missing=policy == "match")
            finite = np.isfinite(expected) & np.isfinite(actual)
            _require(finite.any(), f"{tv}: no finite comparison values")
            # The exported TradingView value is the relative-tolerance reference.
            matched = np.isclose(actual, expected, atol=atol, rtol=rtol, equal_nan=policy == "match")
            details = {"finite_pair_count": int(finite.sum()),
                       "tv_nan_count": int(np.isnan(expected).sum()), "python_nan_count": int(np.isnan(actual).sum()),
                       "max_absolute_error": float(np.max(np.abs(actual[finite] - expected[finite])))}
        failures = np.flatnonzero(~matched)
        results.append({**mapping, **details, "matched": not len(failures), "mismatch_count": len(failures),
                        "first_mismatch_timestamps": [bars.index[i].isoformat() for i in failures[:10]]})
    report = {"schema_version": 1, "status": "matched" if all(row["matched"] for row in results) else "mismatch",
            "script_id": entry["script_id"], "fixture_identity_sha256": entry["fixture_identity_sha256"],
            "source": metadata["source"], "capture": metadata["capture"], "parameters": metadata["parameters"],
            "input_ohlcv_sha256": digest, "tradingview_csv_sha256": external.attrs["csv_sha256"],
            "metadata_sha256": hash_json(metadata), "validator_sha256": validator_hash,
            "calculation_environment": {"python": platform.python_version(), "numpy": np.__version__,
                                        "pandas": pd.__version__},
            "local_mode": mode, "local_metadata": local_metadata,
            "rows": len(bars), "comparison": results, "active_pool_admission": False,
            "origin_authenticated": False,
            "scope_note": "Only the declared columns/history are compared. Capture and precomputed provenance are user attestations. No admission or other-scope parity is implied."}
    _assert_report_inputs_stable(report, csv_path, local_csv)
    return report


def _assert_report_inputs_stable(report, csv_path, local_csv):
    _require(file_sha256(csv_path) == report["tradingview_csv_sha256"], "TradingView CSV changed during comparison")
    if local_csv is not None:
        _require(file_sha256(local_csv) == report["local_metadata"]["csv_sha256"], "local CSV changed during comparison")
    _require(file_sha256(__file__) == report["validator_sha256"], "validator changed during comparison")
    _require(_entry(report["script_id"])["fixture_identity_sha256"] == report["fixture_identity_sha256"],
             "source/runtime identity changed during comparison")


def _report_destination(path, inputs):
    target = Path(path).resolve()
    for input_path in inputs:
        source = Path(input_path).resolve()
        _require(target != source and not (target.exists() and target.samefile(source)),
                 "report destination aliases an intake file")
    return target


def _write_report(path, result):
    # Replacing a directory entry avoids following a late-created output symlink
    # or truncating a hard-linked evidence inode.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".tv-report-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    template = commands.add_parser("template", help="emit incomplete metadata requiring chart verification")
    template.add_argument("--csv", required=True)
    template.add_argument("--script-id", required=True)
    template.add_argument("--timezone", required=True)
    template.add_argument("--time-column", required=True)
    template.add_argument("--timestamp-encoding", choices=("iso8601", "unix_s", "unix_ms"), required=True)
    template.add_argument("--ohlcv-columns", nargs=5, metavar=("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"), required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--csv", required=True)
    validate.add_argument("--metadata", required=True)
    validate.add_argument("--local-csv")
    validate.add_argument("--local-metadata")
    validate.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        if args.command == "template":
            spec = {"timestamp_column": args.time_column, "timestamp_encoding": args.timestamp_encoding,
                    "timestamp_semantics": "bar_open", "ohlcv_columns": dict(zip(OHLCV, args.ohlcv_columns))}
            result = prepare_template(args.csv, args.script_id, spec, args.timezone)
        else:
            inputs = [p for p in (args.csv, args.metadata, args.local_csv, args.local_metadata) if p is not None]
            target = _report_destination(args.report, inputs)
            hashes = {p: file_sha256(p) for p in inputs}
            result = compare_fixture(args.csv, load_metadata(args.metadata), local_csv=args.local_csv,
                                     local_metadata=load_metadata(args.local_metadata) if args.local_metadata else None)
            _require(all(file_sha256(p) == digest for p, digest in hashes.items()), "intake files changed before report write")
            _assert_report_inputs_stable(result, args.csv, args.local_csv)
            result["metadata_file_sha256"] = hashes[args.metadata]
            if args.local_metadata:
                result["local_metadata_file_sha256"] = hashes[args.local_metadata]
            _report_destination(target, inputs)
            _write_report(target, result)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result.get("status", "matched") == "matched" else 1
    except (ValueError, TypeError, KeyError, OSError, csv.Error) as error:
        parser.exit(2, f"fixture validation failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
