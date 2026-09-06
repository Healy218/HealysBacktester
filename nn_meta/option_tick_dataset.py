"""Immutable, request-bound option tick features; no outcome-based selection.

The caller selects contracts from contemporaneous raw spot/chain evidence.
This module validates declared chronology and exact coverage, verifies original
Massive captures, and joins by immutable request identity. Historical SIP
availability does not establish historical local receipt latency or admission.
"""
from __future__ import annotations

from collections import defaultdict
from importlib import metadata as package_metadata
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
import platform
import re

import pandas as pd

from options.data.massive_ticks import TickDataError, canonical_bytes, integer_ns
from options.data.provider import parse_occ_symbol
from options.tick_features import verified_window_features, window_features
from scripts.capture_option_ticks import load_verified_capture

SCHEMA = "option-tick-dataset-v1"
MAX_CAPTURE_NS = 86_400_000_000_000
KEY_COLUMNS = ("symbol", "contract", "window_start_ns", "window_end_ns", "decision_close_ns")
NUMERIC_FEATURES = (
    "opt_tick_spread_bps", "opt_tick_size_imbalance", "opt_tick_valid_quote_fraction",
    "opt_tick_quote_age_seconds", "opt_tick_quote_updates_per_second",
    "opt_tick_trade_count_per_second", "opt_tick_trade_volume_per_second",
    "opt_tick_trade_vwap_mid_bps", "opt_tick_signed_volume_fraction",
    "opt_tick_classified_volume_fraction",
)
AUDIT_COLUMNS = (
    "reported_trade_count", "reported_contract_volume", "reported_trade_vwap",
    "eligible_trade_count", "eligible_contract_volume", "eligible_trade_vwap",
    "condition_excluded_trade_count", "condition_excluded_contract_volume",
)
TABLE_COLUMNS = ("request_id", *KEY_COLUMNS, "option_tick_status", *NUMERIC_FEATURES, *AUDIT_COLUMNS)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,24}\Z")
_SOURCE_FILES = (
    "nn_meta/option_tick_dataset.py", "nn_meta/decision_contracts.py", "options/tick_features.py",
    "options/data/massive_ticks.py", "options/data/provider.py", "options/data/hybrid_provider.py",
    "options/selection/contract_selector.py", "nn_meta/price_basis.py", "scripts/capture_option_ticks.py",
)


def _hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _ns(value):
    value = integer_ns(value)
    if value > 2**63 - 1:
        raise TickDataError("timestamp exceeds exact signed-int64 storage")
    return value


def _path(value):
    path = Path(value).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise TickDataError("immutable input/output paths must not contain symlinks")
    return path.resolve()


def _file_hash(path):
    path = _path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise TickDataError("input changed while hashing")
    return digest.hexdigest()


def _references(paths):
    result = []
    for value in paths:
        path = _path(value)
        if (path.name.startswith(".env") or path.suffix.lower() not in
                (".json", ".md", ".txt", ".csv", ".parquet", ".pdf")):
            raise TickDataError("reference must be an explicit noncredential evidence file")
        result.append({"path": str(path), "sha256": _file_hash(path)})
    if len({r["path"] for r in result}) != len(result):
        raise TickDataError("duplicate evidence reference")
    return sorted(result, key=lambda r: r["path"])


def _verify_references(records):
    if not isinstance(records, list) or any(not isinstance(r, dict) or set(r) != {"path", "sha256"}
                                            for r in records):
        raise TickDataError("invalid evidence references")
    current = _references([r["path"] for r in records])
    if current != records:
        raise TickDataError("evidence reference bytes changed")


def implementation_identity():
    root = Path(__file__).resolve().parents[1]
    return {"source_sha256": {name: _file_hash(root / name) for name in _SOURCE_FILES},
            "runtime": {"python": platform.python_version(),
                        **{name: package_metadata.version(name) for name in ("numpy", "pandas", "pyarrow")}}}


def feature_policy(*, max_quote_age_ns=30_000_000_000, allowed_trade_conditions=(),
                   condition_reference_paths=(), condition_policy_id="no-trade-conditions-admitted"):
    """Explicit eligible-print policy; code 209 needs the caller's bound evidence.

    References preserve the caller's reviewed decision, not an automatic
    interpretation of a provider code. Empty/unknown conditions are excluded.
    The existing raw feature engine's global defaults are never changed.
    """
    codes = list(allowed_trade_conditions)
    if any(isinstance(c, bool) or not isinstance(c, Integral) or c < 0 for c in codes):
        raise TickDataError("condition policy requires Massive integer codes")
    codes = [int(c) for c in codes]
    if len(set(codes)) != len(codes):
        raise TickDataError("condition allowlist has duplicates")
    references = _references(condition_reference_paths)
    age = _ns(max_quote_age_ns)
    if not age or not isinstance(condition_policy_id, str) or not condition_policy_id.strip():
        raise TickDataError("explicit quote-age and condition policy identity required")
    if codes and not references:
        raise TickDataError("admitted trade conditions require bound reference evidence")
    return {"schema": SCHEMA, "availability": "sip", "condition_namespace": "massive_integer",
            "allowed_trade_conditions": sorted(codes), "allow_unconditioned_trades": False,
            "condition_policy_id": condition_policy_id, "condition_references": references,
            "max_quote_age_ns": age, "missing_measurements": "null_without_imputation",
            "model_admission": False}


def _verify_policy(policy):
    if not isinstance(policy, dict):
        raise TickDataError("invalid feature policy")
    try:
        _verify_references(policy["condition_references"])
        expected = feature_policy(max_quote_age_ns=policy["max_quote_age_ns"],
            allowed_trade_conditions=policy["allowed_trade_conditions"],
            condition_reference_paths=[r["path"] for r in policy["condition_references"]],
            condition_policy_id=policy["condition_policy_id"])
    except (KeyError, TypeError) as exc:
        raise TickDataError("invalid feature policy") from exc
    if policy != expected:
        raise TickDataError("unsupported or changed feature policy")


def _key(record):
    try:
        symbol = record["symbol"]
        contract = record["contract"]
        if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol.upper()):
            raise TickDataError("invalid underlying symbol")
        if contract is not None:
            if not isinstance(contract, str):
                raise TickDataError("invalid OCC contract")
            contract = contract.upper().removeprefix("O:")
            parse_occ_symbol(contract)
        start, end, decision = (_ns(record[c]) for c in KEY_COLUMNS[2:])
    except (KeyError, TypeError) as exc:
        raise TickDataError("exact symbol/contract/window/decision key required") from exc
    if not 0 < end - start <= MAX_CAPTURE_NS or end > decision:
        raise TickDataError("feature window must be positive, at most one day, and end by decision close")
    return dict(zip(KEY_COLUMNS, (symbol.upper(), contract, start, end, decision)))


def request_id(record):
    """Stable exact identity, including an explicit null OCC for unselected rows."""
    return _hash({"schema": SCHEMA, **_key(record)})


def _request(record, aliases):
    allowed = {*KEY_COLUMNS, "request_id", "status", "reason", "selected_at_ns",
               "raw_spot_available_ns", "raw_spot", "chain_available_ns", "consumer_ids",
               "selection_policy", "right", "target_dte", "selection_contexts"}
    if not isinstance(record, dict) or set(record) - allowed:
        raise TickDataError("request contains unsupported fields; execution outcomes are not selection inputs")
    key = _key(record)
    status = record.get("status", "selected")
    result = {**key, "status": status, "reason": record.get("reason")}
    if status not in ("selected", "unselected"):
        raise TickDataError("request status must be selected or unselected")
    if status == "selected":
        if key["contract"] is None or result["reason"] is not None:
            raise TickDataError("selected request requires a contract and no exclusion reason")
        root = parse_occ_symbol(key["contract"])[0]
        if aliases.get(root, root) != key["symbol"]:
            raise TickDataError("OCC root differs from the declared underlying without a bound alias")
    evidence_names = ("selected_at_ns", "raw_spot_available_ns", "raw_spot", "chain_available_ns")
    if status == "selected" or any(record.get(c) is not None for c in evidence_names):
        try:
            selected, spot_at, chain_at = (_ns(record[c]) for c in
                ("selected_at_ns", "raw_spot_available_ns", "chain_available_ns"))
            spot = record["raw_spot"]
        except KeyError as exc:
            raise TickDataError("selected request needs contemporaneous raw spot and chain timestamps") from exc
        if (not isinstance(spot, Real) or isinstance(spot, bool) or not math.isfinite(spot) or spot <= 0
                or not spot_at <= selected <= key["decision_close_ns"] or chain_at > selected):
            raise TickDataError("selection uses invalid raw spot or information after the decision")
        result.update(selected_at_ns=selected, raw_spot_available_ns=spot_at,
                      raw_spot=float(spot), chain_available_ns=chain_at)
    if status == "unselected":
        if key["contract"] is not None or result["reason"] not in (
                "no_chain", "no_contract", "raw_spot_unavailable", "outside_history",
                "no_prior_date_contract_in_selection_band"):
            raise TickDataError("unselected request requires null contract and an explicit selection reason")
    contexts = record.get("selection_contexts", [])
    if not isinstance(contexts, list):
        raise TickDataError("selection contexts must be a list")
    contexts = [dict(c) if isinstance(c, dict) else c for c in contexts]
    if any(c in record for c in ("selection_policy", "right", "target_dte")):
        contexts.append({c: record.get(c) for c in ("selection_policy", "right", "target_dte")})
    for context in contexts:
        if (not isinstance(context, dict) or set(context) != {"selection_policy", "right", "target_dte"}
                or not isinstance(context["selection_policy"], str) or not context["selection_policy"]
                or context["right"] not in ("C", "P")
                or isinstance(context["target_dte"], bool) or not isinstance(context["target_dte"], Integral)
                or context["target_dte"] < 0):
            raise TickDataError("invalid declared selector policy/right/DTE context")
        if key["contract"] is not None and parse_occ_symbol(key["contract"])[2] != context["right"]:
            raise TickDataError("selector context right differs from OCC contract")
        context["target_dte"] = int(context["target_dte"])
    result["selection_contexts"] = sorted({_hash(c): c for c in contexts}.values(), key=_hash)
    consumers = record.get("consumer_ids", [])
    if not isinstance(consumers, list) or any(not isinstance(c, str) or not c for c in consumers):
        raise TickDataError("consumer_ids must be explicit nonempty strings")
    result["consumer_ids"] = sorted(set(consumers))
    result["request_id"] = request_id(key)
    if record.get("request_id", result["request_id"]) != result["request_id"]:
        raise TickDataError("declared request_id does not match its exact key")
    return result


def create_task_manifest(requests, *, selection_reference_paths, feature_policy,
                         root_aliases=None, output_path=None):
    """Deduplicate shared decisions, bind evidence, and freeze required coverage.

    References must describe pre-decision raw spot/chain selection. A hash
    preserves that declaration; it cannot establish the truth of a fabricated
    selector. Root aliases are explicit and covered by the task identity.
    """
    _verify_policy(feature_policy)
    references = _references(selection_reference_paths)
    if not references:
        raise TickDataError("selection evidence references are required")
    aliases = dict(root_aliases or {})
    if any(not isinstance(k, str) or not isinstance(v, str) or not _SYMBOL.fullmatch(k)
           or not _SYMBOL.fullmatch(v) for k, v in aliases.items()):
        raise TickDataError("invalid explicit root alias mapping")
    merged = {}
    for raw in requests:
        req = _request(raw, aliases)
        prior = merged.get(req["request_id"])
        if prior is not None:
            if {k: v for k, v in prior.items() if k not in ("consumer_ids", "selection_contexts")} != {
                    k: v for k, v in req.items() if k not in ("consumer_ids", "selection_contexts")}:
                raise TickDataError("ambiguous selection metadata for the same exact request key")
            req["consumer_ids"] = sorted(set(req["consumer_ids"]) | set(prior["consumer_ids"]))
            req["selection_contexts"] = sorted({_hash(c): c for c in
                req["selection_contexts"] + prior["selection_contexts"]}.values(), key=_hash)
        merged[req["request_id"]] = req
    if not merged:
        raise TickDataError("task must contain explicit decision requests")
    task = {"schema": SCHEMA, "selection_basis": "pre_decision_raw_spot_and_chain",
            "selection_references": references, "root_aliases": aliases,
            "feature_policy": feature_policy, "implementation": implementation_identity(),
            "requests": sorted(merged.values(), key=lambda r: r["request_id"]),
            "numeric_features": list(NUMERIC_FEATURES), "model_admission": False}
    task["task_sha256"] = _hash(task)
    if output_path is not None:
        path = _path(output_path)
        with path.open("x") as stream:
            stream.write(canonical_bytes(task).decode() + "\n")
    return task


def _verify_task(task):
    if not isinstance(task, dict) or task.get("schema") != SCHEMA:
        raise TickDataError("invalid task manifest")
    digest = task.get("task_sha256")
    if not isinstance(digest, str) or not _HASH.fullmatch(digest) or digest != _hash(
            {k: v for k, v in task.items() if k != "task_sha256"}):
        raise TickDataError("task manifest hash mismatch")
    if task.get("implementation") != implementation_identity():
        raise TickDataError("feature source or runtime changed since task creation")
    _verify_references(task.get("selection_references"))
    _verify_policy(task.get("feature_policy"))
    rebuilt = create_task_manifest(task["requests"],
        selection_reference_paths=[r["path"] for r in task["selection_references"]],
        feature_policy=task["feature_policy"], root_aliases=task.get("root_aliases"))
    if task != rebuilt:
        raise TickDataError("task metadata or request inventory is inconsistent")


def load_task_manifest(path, *, expected_task_sha256):
    """Verify a persisted task against its separately recorded review anchor."""
    path = _path(path)
    before = _file_hash(path)
    task = json.loads(path.read_bytes())
    _verify_task(task)
    if task["task_sha256"] != expected_task_sha256 or _file_hash(path) != before:
        raise TickDataError("task bytes or expected review anchor changed")
    return task


def plan_capture_windows(task, *, max_span_ns=MAX_CAPTURE_NS, max_gap_ns=0):
    """Coalesce per-contract overlap/touch; never silently bridge a gap by default."""
    _verify_task(task)
    span, gap = _ns(max_span_ns), _ns(max_gap_ns)
    if not 0 < span <= MAX_CAPTURE_NS:
        raise TickDataError("capture planning span must be positive and at most one day")
    grouped = defaultdict(list)
    for req in task["requests"]:
        if req["status"] == "selected":
            if req["window_end_ns"] - req["window_start_ns"] > span:
                raise TickDataError("required window exceeds capture planning span")
            grouped[req["contract"]].append(req)
    planned = []
    for contract, requests in sorted(grouped.items()):
        for req in sorted(requests, key=lambda r: (r["window_start_ns"], r["window_end_ns"])):
            start, end = req["window_start_ns"], req["window_end_ns"]
            prev = planned[-1] if planned and planned[-1]["contract"] == contract else None
            if prev and start <= prev["end_ns"] + gap and max(end, prev["end_ns"]) - prev["start_ns"] <= span:
                prev["end_ns"] = max(end, prev["end_ns"])
                prev["request_ids"].append(req["request_id"])
            else:
                planned.append({"contract": contract, "start_ns": start, "end_ns": end,
                                "request_ids": [req["request_id"]]})
    return planned


def compute_feature_row(reported, metadata, *, eligible):
    """Normalize canonical raw and genuinely condition-filtered window results.

    Both results must use the same quote history/window/availability. Eligible
    counts/VWAP are never copied from unfiltered reported statistics. This pure
    function can also normalize a verified receipt-based live window later.
    """
    key = _key(metadata)
    if key["contract"] is None:
        raise TickDataError("numeric feature rows require a selected OCC contract")
    if reported.get("schema") != "option-tick-features-v1" or eligible.get("schema") != reported["schema"]:
        raise TickDataError("canonical window_features results required")
    quote_fields = ("availability_basis", "quote_updates", "valid_quote_time_fraction",
                    "time_weighted_spread_bps", "time_weighted_size_imbalance",
                    "last_quote_age_seconds", "last_bid", "last_ask")
    if any(reported.get(k) != eligible.get(k) for k in quote_fields):
        raise TickDataError("reported and eligible results use different quote windows")
    if reported["availability_basis"] not in ("sip", "receipt"):
        raise TickDataError("unsupported feature availability basis")
    seconds = (key["window_end_ns"] - key["window_start_ns"]) / 1e9
    age = reported["last_quote_age_seconds"]
    if age is not None:
        age += (key["decision_close_ns"] - key["window_end_ns"]) / 1e9
    mid = ((reported["last_bid"] + reported["last_ask"]) / 2
           if reported["last_bid"] is not None and reported["last_ask"] is not None else None)
    volume, vwap = eligible["reported_contract_volume"], eligible["reported_trade_vwap"]
    classified = eligible["quote_test_classified_volume_fraction"]
    values = (reported["time_weighted_spread_bps"], reported["time_weighted_size_imbalance"],
              reported["valid_quote_time_fraction"], age, reported["quote_updates"] / seconds,
              eligible["reported_trade_count"] / seconds, volume / seconds,
              (vwap / mid - 1) * 1e4 if vwap is not None and mid is not None else None,
              eligible["quote_test_signed_volume"] / volume if volume and classified else None,
              classified)
    row = {"request_id": request_id(key), **key, "option_tick_status": "covered"}
    for name, value in zip(NUMERIC_FEATURES, values):
        if value is not None and (isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value)):
            raise TickDataError("feature calculation produced a nonfinite or nonnumeric measurement")
        row[name] = float(value) if value is not None else None
    row.update(reported_trade_count=reported["reported_trade_count"],
               reported_contract_volume=reported["reported_contract_volume"],
               reported_trade_vwap=reported["reported_trade_vwap"],
               eligible_trade_count=eligible["reported_trade_count"],
               eligible_contract_volume=volume, eligible_trade_vwap=vwap,
               condition_excluded_trade_count=reported["reported_trade_count"] - eligible["reported_trade_count"],
               condition_excluded_contract_volume=reported["reported_contract_volume"] - volume)
    if row["condition_excluded_trade_count"] < 0 or row["condition_excluded_contract_volume"] < 0:
        raise TickDataError("eligible trade results are not a subset of reported observations")
    return row


def _capture_identity(directory, report):
    directory = _path(directory)
    names = {"manifest.json"}
    for entry in report["contracts"]:
        for kind in ("quotes", "trades"):
            names.add(f"{entry['contract']}.{kind}.json.gz")
    return {"directory": str(directory),
            "files_sha256": {name: _file_hash(directory / name) for name in sorted(names)}}


def _verify_capture_identity(identity):
    directory = _path(identity["directory"])
    manifest_path = directory / "manifest.json"
    if _file_hash(manifest_path) != identity["files_sha256"]["manifest.json"]:
        raise TickDataError("capture manifest bytes changed")
    report = json.loads(manifest_path.read_bytes())
    if _capture_identity(directory, report) != identity:
        raise TickDataError("capture bytes or file inventory changed")
    return report


def _eligible_trade(row, allowed):
    conditions = row.get("conditions")
    return (isinstance(conditions, list) and bool(conditions)
            and all(isinstance(c, int) and not isinstance(c, bool) and c in allowed for c in conditions))


def materialize_store(task, capture_directories, output_dir):
    """Require every selected window, publish manifest last, and never overwrite.

    A required window must fit inside one verified bundle. Partial overlapping
    captures are not stitched or treated as full coverage. Multiple suitable
    bundles are ambiguous and require an explicit upstream choice.
    """
    _verify_task(task)
    output = _path(output_dir)
    if output.exists():
        raise TickDataError("feature store output must be a fresh immutable directory")
    directories = [_path(d) for d in capture_directories]
    if len(set(directories)) != len(directories):
        raise TickDataError("duplicate capture directory")
    if any(output.is_relative_to(d) for d in directories):
        raise TickDataError("feature output must not modify a raw capture directory")
    catalog, identities = [], []
    for directory in directories:
        manifest_path = directory / "manifest.json"
        before = _file_hash(manifest_path)
        report, captures = load_verified_capture(directory)
        identity = _capture_identity(directory, report)
        if identity["files_sha256"]["manifest.json"] != before:
            raise TickDataError("capture manifest changed while loading")
        identities.append(identity)
        entries = {entry["contract"]: entry for entry in report["contracts"]}
        catalog.append((report, captures, entries, identity))
    rows, coverage = [], {}
    policy = task["feature_policy"]
    computed = {}
    for req in task["requests"]:
        if req["status"] == "unselected":
            rows.append({"request_id": req["request_id"], **{k: req[k] for k in KEY_COLUMNS},
                         "option_tick_status": "unselected",
                         **dict.fromkeys((*NUMERIC_FEATURES, *AUDIT_COLUMNS))})
            continue
        candidates = [item for item in catalog if req["contract"] in item[1]
                      and item[0]["plan"]["start_ns"] <= req["window_start_ns"]
                      and req["window_end_ns"] <= item[0]["plan"]["end_ns"]]
        if len(candidates) != 1:
            raise TickDataError("required window has missing or ambiguous verified capture coverage: " + req["request_id"])
        report, captures, entries, identity = candidates[0]
        contract = req["contract"]
        window_key = (contract, req["window_start_ns"], req["window_end_ns"])
        if window_key not in computed:
            data, entry = captures[contract], entries[contract]
            kwargs = {"start_ns": req["window_start_ns"], "end_ns": req["window_end_ns"],
                      "max_quote_age_ns": policy["max_quote_age_ns"],
                      "allowed_trade_conditions": policy["allowed_trade_conditions"],
                      "allow_unconditioned_trades": False}
            reported = verified_window_features(data["quotes"], data["trades"],
                quote_manifest=entry["captures"]["quotes"], trade_manifest=entry["captures"]["trades"],
                contract=contract, **kwargs)
            # Raw rows/manifests have already been verified intact. Filter only
            # the derived eligible view, preserving quote order and raw hashes.
            allowed = set(policy["allowed_trade_conditions"])
            filtered = [row for row in data["trades"] if _eligible_trade(row, allowed)]
            eligible = window_features(data["quotes"], filtered, complete=True,
                coverage_start_ns=report["plan"]["start_ns"],
                coverage_end_ns=report["plan"]["end_ns"], **kwargs)
            computed[window_key] = reported, eligible
        reported, eligible = computed[window_key]
        rows.append(compute_feature_row(reported, req, eligible=eligible))
        coverage[req["request_id"]] = {"capture_manifest_sha256": identity["files_sha256"]["manifest.json"],
                                       "directory": identity["directory"], "contract": contract,
                                       "start_ns": req["window_start_ns"], "end_ns": req["window_end_ns"]}
    output.mkdir(parents=True, exist_ok=False)
    task_path, rows_path = output / "task.json", output / "features.parquet"
    task_path.write_bytes(canonical_bytes(task) + b"\n")
    frame = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    for column in KEY_COLUMNS[2:]:
        frame[column] = pd.array([row[column] for row in rows], dtype="int64")
    for column in NUMERIC_FEATURES:
        frame[column] = pd.array([row[column] for row in rows], dtype="Float64")
    frame.to_parquet(rows_path, index=False)
    _verify_task(task)
    for identity in identities:
        _verify_capture_identity(identity)
    _verify_task(task)
    manifest = {"schema": SCHEMA, "complete": True, "task_sha256": task["task_sha256"],
                "task_file_sha256": _file_hash(task_path), "features_sha256": _file_hash(rows_path),
                "numeric_features": list(NUMERIC_FEATURES), "row_count": len(rows),
                "selected_request_count": len(coverage), "unselected_request_count": len(rows) - len(coverage),
                "coverage": coverage, "captures": identities, "implementation": task["implementation"],
                "feature_policy": policy, "model_admission": False}
    manifest["store_sha256"] = _hash(manifest)
    (output / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    return manifest


def load_feature_store(directory, *, expected_task_sha256, expected_store_sha256, expected_policy=None):
    """Read only with external task/store hash anchors; reject stale source/data."""
    directory = _path(directory)
    if {p.name for p in directory.iterdir()} != {"manifest.json", "task.json", "features.parquet"}:
        raise TickDataError("feature store is incomplete or its file inventory changed")
    manifest_path = directory / "manifest.json"
    _path(manifest_path)  # reject a replaced manifest symlink before reading it
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest.get("schema") != SCHEMA or manifest.get("complete") is not True
            or manifest.get("model_admission") is not False
            or manifest.get("numeric_features") != list(NUMERIC_FEATURES)
            or manifest.get("task_sha256") != expected_task_sha256
            or manifest.get("store_sha256") != expected_store_sha256
            or expected_store_sha256 != _hash({k: v for k, v in manifest.items() if k != "store_sha256"})):
        raise TickDataError("feature store manifest or external hash anchor mismatch")
    task_path, rows_path = directory / "task.json", directory / "features.parquet"
    if (_file_hash(task_path) != manifest["task_file_sha256"]
            or _file_hash(rows_path) != manifest["features_sha256"]):
        raise TickDataError("feature store task or row bytes changed")
    task = json.loads(task_path.read_bytes())
    _verify_task(task)
    if (task["task_sha256"] != expected_task_sha256 or manifest["implementation"] != task["implementation"]
            or manifest["feature_policy"] != task["feature_policy"]
            or expected_policy is not None and expected_policy != task["feature_policy"]):
        raise TickDataError("feature store provenance or feature policy mismatch")
    capture_metadata = [(_verify_capture_identity(identity), identity) for identity in manifest["captures"]]
    frame = pd.read_parquet(rows_path)
    expected_ids = {r["request_id"] for r in task["requests"]}
    selected_ids = {r["request_id"] for r in task["requests"] if r["status"] == "selected"}
    if (tuple(frame.columns) != TABLE_COLUMNS or frame.request_id.duplicated().any()
            or set(frame.request_id) != expected_ids or len(frame) != manifest["row_count"]
            or set(manifest["coverage"]) != selected_ids
            or manifest["selected_request_count"] != len(selected_ids)
            or manifest["unselected_request_count"] != len(expected_ids - selected_ids)):
        raise TickDataError("feature store row keys or required coverage inventory mismatch")
    requests = {r["request_id"]: r for r in task["requests"]}
    for rid in selected_ids:
        req = requests[rid]
        matched = [(report, identity) for report, identity in capture_metadata
                   if req["contract"] in report["plan"]["contracts"]
                   and report["plan"]["start_ns"] <= req["window_start_ns"]
                   and req["window_end_ns"] <= report["plan"]["end_ns"]]
        if len(matched) != 1:
            raise TickDataError("required coverage manifest has missing or ambiguous captures")
        identity = matched[0][1]
        expected = {"capture_manifest_sha256": identity["files_sha256"]["manifest.json"],
                    "directory": identity["directory"], "contract": req["contract"],
                    "start_ns": req["window_start_ns"], "end_ns": req["window_end_ns"]}
        if manifest["coverage"][rid] != expected:
            raise TickDataError("coverage metadata differs from the required contract/window")
    for row in frame.to_dict("records"):
        req = requests[row["request_id"]]
        if _key(row) != {k: req[k] for k in KEY_COLUMNS} or request_id(row) != req["request_id"]:
            raise TickDataError("feature row does not match its exact requested decision key")
        if row["option_tick_status"] != ("covered" if req["status"] == "selected" else "unselected"):
            raise TickDataError("feature row selection status changed")
        if req["status"] == "unselected" and any(pd.notna(row[c]) for c in NUMERIC_FEATURES):
            raise TickDataError("unselected request contains fabricated features")
    if any(not pd.api.types.is_numeric_dtype(frame[c].dtype) for c in NUMERIC_FEATURES):
        raise TickDataError("feature columns must have fixed nullable numeric types")
    for c in NUMERIC_FEATURES:
        if any(not math.isfinite(float(v)) for v in frame[c].dropna()):
            raise TickDataError("nonfinite feature measurement")
    if (_file_hash(rows_path) != manifest["features_sha256"] or _file_hash(task_path) != manifest["task_file_sha256"]
            or manifest_path.read_bytes() != manifest_bytes):
        raise TickDataError("feature store changed during reading")
    _verify_task(task)
    frame.attrs.update(task_sha256=expected_task_sha256, store_sha256=expected_store_sha256,
                       feature_policy=task["feature_policy"], model_admission=False)
    return frame


def join_decisions(decisions, directory, *, expected_task_sha256, expected_store_sha256,
                   allow_unselected=False):
    """Exact many-to-one join; missing windows never become zeros or asof matches."""
    if not isinstance(allow_unselected, bool):
        raise TickDataError("allow_unselected must be an explicit boolean")
    if not isinstance(decisions, pd.DataFrame) or not {"request_id", *KEY_COLUMNS}.issubset(decisions.columns):
        raise TickDataError("decision join requires request_id and the exact decision key")
    if any(c in decisions for c in (*NUMERIC_FEATURES, "option_tick_status")):
        raise TickDataError("decision rows already contain option tick features/status")
    store = load_feature_store(directory, expected_task_sha256=expected_task_sha256,
                               expected_store_sha256=expected_store_sha256)
    indexed = store.set_index("request_id", verify_integrity=True)
    chosen = []
    for row in decisions.to_dict("records"):
        rid = row["request_id"]
        if rid not in indexed.index or request_id(row) != rid:
            raise TickDataError("required decision window is missing or its request key is inconsistent")
        feature = indexed.loc[rid]
        if _key(row) != _key(feature.to_dict()):
            raise TickDataError("decision symbol/OCC/window/asof differs from the feature request")
        if feature.option_tick_status == "unselected" and not allow_unselected:
            raise TickDataError("unselected decision has no tick features; explicit preservation is required")
        chosen.append(feature)
    result = decisions.copy()
    for name in (*NUMERIC_FEATURES, "option_tick_status"):
        values = [r[name] for r in chosen]
        result[name] = pd.array(values, dtype="Float64" if name in NUMERIC_FEATURES else "string")
    result.attrs.update(store.attrs)
    return result
