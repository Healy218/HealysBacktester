"""Sealed inputs and common row projection for the expanded v6 research pool.

The manifest is an external hash anchor, not a self-authorizing admission bit.
Verified runs recheck a captured parity pack before a worker can run. Explicit
comparison deferral uses a separate unverified research contract; context and
tick coverage are still required.
Historical tick coverage is exact per decision; live receipt/condition adapters
remain a separate deployment gate.
"""
from __future__ import annotations

from functools import lru_cache
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.decision_contracts import DecisionContractSelector, POLICY_VERSION
from nn_meta.option_tick_dataset import NUMERIC_FEATURES, join_decisions, request_id, load_feature_store
from nn_meta.tradingview_features import FEATURE_NAMES, tradingview_features, validate_feature_inputs, feature_schema

SCHEMA = "v6-expanded-inputs-v1"
CONTRACT_VERSION = "2026-09-06-tv13-option-ticks-v4"
DEFERRED_CONTRACT_VERSION = "2026-09-06-tv13-option-ticks-unverified-v1"
EXTRA_FEATURES = (*FEATURE_NAMES, *NUMERIC_FEATURES)


def sha256(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("expanded inputs cannot contain symlinks")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError("expanded input changed while reading")
    return digest.hexdigest()


def aware_bars(bars):
    result = bars.copy()
    result.attrs = {}
    result.index = pd.DatetimeIndex(result.index)
    result.index = (result.index.tz_localize("UTC") if result.index.tz is None
                    else result.index.tz_convert("UTC"))
    return result


def bars_sha256(bars):
    bars = aware_bars(bars)
    return hashlib.sha256(bars.index.as_unit("ns").asi8.astype("<i8").tobytes()
        + bars[["Open", "High", "Low", "Close", "Volume"]].to_numpy(dtype="<f8").tobytes()).hexdigest()


class ExpandedInputs:
    def __init__(self, path, expected_sha256, *, parity_policy="verified"):
        if parity_policy not in ("verified", "deferred"):
            raise ValueError("parity policy must be verified or deferred")
        self.parity_policy = parity_policy
        self.path = Path(path).absolute()
        if not expected_sha256 or sha256(self.path) != expected_sha256:
            raise ValueError("expanded input manifest differs from external SHA256 anchor")
        self.digest = expected_sha256
        self.document = json.loads(self.path.read_bytes())
        doc = self.document
        contract = DEFERRED_CONTRACT_VERSION if parity_policy == "deferred" else CONTRACT_VERSION
        if (doc.get("schema") != SCHEMA or doc.get("feature_contract_version") != contract
                or doc.get("feature_names") != list(EXTRA_FEATURES)
                or doc.get("selection_policy") != POLICY_VERSION
                or not isinstance(doc.get("symbols"), dict) or not doc["symbols"]):
            raise ValueError("expanded manifest requires the complete TV13/tick schema and selection policy")
        if (not doc.get("tick_feature_policy", {}).get("allowed_trade_conditions")
                or not doc["tick_feature_policy"].get("condition_references")):
            raise ValueError("expanded quote/trade features require an explicit evidence-bound eligible-trade policy")
        if parity_policy == "deferred":
            declaration = doc.get("external_comparison", {})
            if (declaration.get("status") != "deferred"
                    or declaration.get("research_only") is not True
                    or not isinstance(declaration.get("reason"), str)
                    or not declaration["reason"].strip()
                    or "parity_pack" in doc):
                raise ValueError("deferred comparison requires an explicit research-only declaration and no parity pack")
            self.parity = None
            self.expected_feature_schema = doc["feature_schema"]
            self.bound_files = {}
        else:
            if "external_comparison" in doc:
                raise ValueError("verified inputs cannot contain a comparison waiver")
            from nn_meta.v6_admission import verify_parity_pack
            pack = self.reference(doc["parity_pack"])
            self.parity = verify_parity_pack(pack, doc["parity_pack"]["sha256"])
            self.expected_feature_schema = self.parity["feature_schema"]
            self.bound_files = dict(self.parity["input_files"])
            self.bound_files.update(self.parity["verification_runtime_sha256"])
        self.bound_files[str(self.path)] = self.digest
        for record in doc.get("context_references", []):
            self.bound_files[str(self.reference(record))] = record["sha256"]
        self._contexts = {}
        self._matrices = {}
        self.assert_unchanged()

    def reference(self, record):
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("input references need exact path and SHA256")
        path = Path(record["path"])
        if not path.is_absolute():
            path = self.path.parent / path
        if sha256(path) != record["sha256"]:
            raise ValueError(f"expanded input bytes changed: {path.name}")
        return path

    def assert_unchanged(self):
        if sha256(self.path) != self.digest:
            raise ValueError("expanded manifest changed during work")
        if self.parity_policy == "verified":
            self.reference(self.document["parity_pack"])
        for path, digest in self.bound_files.items():
            if sha256(path) != digest:
                raise ValueError(f"expanded evidence or runtime changed: {Path(path).name}")
        for entry in self.document["symbols"].values():
            self.reference(entry["timeframe_flags"])
            if entry.get("vwap_observations") is not None:
                self.reference(entry["vwap_observations"])

    def context(self, symbol, bars):
        symbol = symbol.upper()
        if symbol not in self.document["symbols"]:
            raise ValueError(f"expanded inputs missing symbol {symbol}")
        entry = self.document["symbols"][symbol]
        if bars_sha256(bars) != entry["bars_sha256"]:
            raise ValueError(f"expanded {symbol} history bytes/origin differ from the sealed context")
        if symbol not in self._contexts:
            context = dict(entry["context"])
            if context["dependency_metadata"]["symbol"] != symbol:
                raise ValueError("context symbol differs from requested underlying")
            context["timeframe_flags"] = pd.read_parquet(self.reference(entry["timeframe_flags"]))
            if entry.get("vwap_observations") is not None:
                context["vwap_observations"] = pd.read_parquet(self.reference(entry["vwap_observations"]))
            actual_schema = feature_schema(minimum_tick=context["minimum_tick"],
                session_policy=context.get("session_policy", "strict"),
                vwap_mode="observed" if "vwap_observations" in context else "reset_flags")
            if actual_schema != self.expected_feature_schema:
                raise ValueError("runtime tick/session/VWAP/default feature scope differs from the verified parity pack or declared research schema")
            validate_feature_inputs(aware_bars(bars), **context)
            self._contexts[symbol] = context
        self.assert_unchanged()
        return deepcopy(self._contexts[symbol])

    def attach(self, symbol, bars):
        bars.attrs["v6_tradingview_context"] = self.context(symbol, bars)
        return bars

    def matrix(self, symbol, bars):
        context = self.context(symbol, bars)
        if symbol not in self._matrices:
            self._matrices[symbol] = tradingview_features(aware_bars(bars), **context)
        return self._matrices[symbol]

    def bind_tick_stores(self, symbols):
        """Verify stores before expensive work; expose transitive campaign inputs."""
        for symbol in symbols:
            if symbol not in self.document["symbols"]:
                raise ValueError(f"expanded inputs missing {symbol}")
            entry = self.document["symbols"][symbol]["tick_store"]
            directory = Path(entry["directory"])
            if not directory.is_absolute():
                directory = self.path.parent / directory
            load_feature_store(directory, expected_task_sha256=entry["task_sha256"],
                expected_store_sha256=entry["store_sha256"], expected_policy=self.document["tick_feature_policy"])
            manifest = json.loads((directory / "manifest.json").read_bytes())
            task = json.loads((directory / "task.json").read_bytes())
            for name in ("manifest.json", "task.json", "features.parquet"):
                self.bound_files[str(directory / name)] = sha256(directory / name)
            for ref in task["selection_references"] + task["feature_policy"]["condition_references"]:
                self.bound_files[ref["path"]] = ref["sha256"]
            for capture in manifest["captures"]:
                for name, digest in capture["files_sha256"].items():
                    self.bound_files[str(Path(capture["directory"]) / name)] = digest
        self.assert_unchanged()

    def input_files(self):
        paths = dict(self.bound_files)
        for entry in self.document["symbols"].values():
            for field in ("timeframe_flags", "vwap_observations"):
                if entry.get(field) is not None:
                    paths[str(self.reference(entry[field]))] = entry[field]["sha256"]
        return paths

    def append(self, rows, *, symbol, bars, provider, raw_close):
        """Same exact decision keys/features for historical and replay candidates.

        Contract labels are checked when present; an unfilled trade may have a
        null executed contract while its independently selected contract exists.
        No selection uses those execution columns.
        """
        if rows.empty:
            return rows.copy()
        if set(rows.symbol) != {symbol} or any(name in rows for name in EXTRA_FEATURES):
            raise ValueError("expanded row projection requires one symbol and no preexisting extra features")
        from nn_meta.price_basis import require_raw_close
        require_raw_close(raw_close)
        if raw_close.attrs["symbol"] != symbol:
            raise ValueError("raw spot belongs to a different symbol")
        matrix = self.matrix(symbol, bars)
        selector = DecisionContractSelector(provider, moneyness=self.document.get("moneyness", 0.0))
        requested = []
        selected_features = []
        for row in rows.to_dict("records"):
            if (row["direction"] not in (0, 1) or isinstance(row["dte"], bool)
                    or not isinstance(row["dte"], (int, np.integer)) or row["dte"] < 0):
                raise ValueError("decision direction and DTE must be explicit 0/1 and nonnegative integer")
            stamp = pd.Timestamp(row["entry_ts"])
            stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
            naive = stamp.tz_localize(None)
            if naive not in raw_close.index or stamp not in matrix.values.index:
                raise ValueError("decision lacks an exact raw spot or technical feature bar")
            if matrix.available_at.loc[stamp] > stamp + pd.Timedelta(minutes=15):
                raise ValueError("technical feature was unavailable at decision close")
            req = selector.request(symbol, signal_bar_open=stamp,
                right="P" if bool(row["direction"]) else "C", raw_spot=float(raw_close.loc[naive]),
                target_dte=int(row["dte"]))
            label = row.get("contract")
            if label is not None and pd.notna(label) and label.removeprefix("O:") != req["contract"]:
                raise ValueError("label contract differs from independently selected feature contract")
            req["request_id"] = request_id(req)
            requested.append(req)
            selected_features.append(matrix.values.loc[stamp])
        entry = self.document["symbols"][symbol]["tick_store"]
        directory = Path(entry["directory"])
        if not directory.is_absolute():
            directory = self.path.parent / directory
        joined = join_decisions(pd.DataFrame(requested), directory,
            expected_task_sha256=entry["task_sha256"], expected_store_sha256=entry["store_sha256"],
            allow_unselected=True)
        if joined.attrs["feature_policy"] != self.document["tick_feature_policy"]:
            raise ValueError("tick store uses a different frozen condition/availability policy")
        extra = {col: [float(row[col]) for row in selected_features] for col in FEATURE_NAMES}
        extra.update({col: joined[col].to_numpy(dtype=float, na_value=np.nan) for col in NUMERIC_FEATURES})
        extra.update(decision_contract=[row["contract"] for row in requested],
                     option_tick_request_id=joined.request_id.to_numpy(),
                     option_tick_status=joined.option_tick_status.to_numpy())
        result = pd.concat([rows.copy(), pd.DataFrame(extra, index=rows.index)], axis=1)
        result.attrs["v6_inputs_sha256"] = self.digest
        self.assert_unchanged()
        return result


@lru_cache(maxsize=1)
def from_environment():
    from nn_meta import config
    if not config.V6_EXPANDED:
        raise ValueError("expanded inputs require NN_META_V6_EXPANDED=1")
    result = ExpandedInputs(config.V6_INPUTS, config.V6_INPUTS_SHA256,
                            parity_policy=config.V6_PARITY_POLICY)
    if result.document.get("moneyness", 0.0) != config.EXEC_CONFIG.get("MONEYNESS", 0.0):
        raise ValueError("expanded feature and execution moneyness policies differ")
    return result
