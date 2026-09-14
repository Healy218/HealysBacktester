"""Sealed live snapshots for V6 shadow scoring, with explicit receipt clocks.

The snapshot keeps full technical history/origin, separately sourced raw spot,
prior-date contracts, context and capture evidence. It never substitutes a
latest quote for a closed-bar tick window or declares a heartbeat complete.
The receipt-vs-SIP/provider difference remains a forward research limitation.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.decision_contracts import utc_stamp
from nn_meta.option_tick_dataset import NUMERIC_FEATURES, compute_feature_row
from nn_meta.price_basis import require_raw_panel, require_raw_surface
from nn_meta.v6_expansion import ExpandedInputs, bars_sha256, sha256
from options.data.provider import OptionContract, parse_occ_symbol
from options.tick_features import window_features


class SnapshotChain:
    point_in_time_chain = True

    def __init__(self, frame, *, now):
        if not {"symbol", "contract", "first_observed_at", "available_at"} <= set(frame):
            raise ValueError("live chain requires observed and received contract timestamps")
        self.frame = frame.copy()
        for col in ("first_observed_at", "available_at"):
            self.frame[col] = pd.DatetimeIndex([utc_stamp(v) for v in frame[col]])
        if ((self.frame.available_at < self.frame.first_observed_at).any()
                or (self.frame.available_at > now).any()
                or self.frame.duplicated(["symbol", "contract"]).any()):
            raise ValueError("invalid or future live chain evidence")

    def get_chain(self, symbol, *, right, expiration_gte, expiration_lte, as_of):
        cutoff = pd.Timestamp(as_of, tz="UTC") + pd.Timedelta(days=1)
        rows = self.frame[(self.frame.symbol == symbol) &
                          (self.frame.available_at < cutoff) &
                          (self.frame.first_observed_at < cutoff)]
        out = []
        for row in rows.itertuples(index=False):
            contract = row.contract.upper().removeprefix("O:")
            root, expiry, side, strike = parse_occ_symbol(contract)
            if root != symbol:
                raise ValueError("live chain aliases require separately verified historical membership")
            if side == right and expiration_gte <= expiry <= expiration_lte:
                out.append(OptionContract(contract, symbol, expiry, strike, side))
        return out


class ReceiptInputs(ExpandedInputs):
    def join_ticks(self, requested, *, symbol):
        results = []
        for request in requested.to_dict("records"):
            base = {**request, "option_tick_status": "unselected",
                    **{f: np.nan for f in NUMERIC_FEATURES}}
            if request["contract"] is not None:
                base.update(self.snapshot.tick_features(request))
            results.append(base)
        frame = pd.DataFrame(results)
        frame.attrs["feature_policy"] = self.document["tick_feature_policy"]
        return frame


class LiveSnapshot:
    """Hash-bound adapter accepted only by the isolated shadow scan path."""
    research_only = True

    def __init__(self, path, expected_sha256, *, now, max_age_seconds=900):
        self.path = Path(path).absolute()
        self.now = utc_stamp(now)
        self.files = {str(self.path): expected_sha256}
        if not expected_sha256 or sha256(self.path) != expected_sha256:
            raise ValueError("live snapshot differs from external SHA256 anchor")
        self.digest = expected_sha256
        self.document = json.loads(self.path.read_text())
        doc = self.document
        if doc.get("schema") != "v6-live-snapshot-v1":
            raise ValueError("unknown live snapshot schema")
        captured = utc_stamp(doc["captured_at"])
        if not 0 <= (self.now - captured).total_seconds() <= max_age_seconds:
            raise ValueError("live snapshot is stale or from the future")
        context = self.reference(doc["expanded_inputs"])
        self.expanded_inputs = ReceiptInputs(context, doc["expanded_inputs"]["sha256"],
                                             parity_policy=doc["parity_policy"])
        self.expanded_inputs.snapshot = self
        self.bars = pd.read_parquet(self.reference(doc["bars"]))
        if not {"symbol", "timestamp", "available_at", "Open", "High", "Low", "Close", "Volume"} <= set(self.bars):
            raise ValueError("live bars require OHLCV and receipt timestamps")
        if (self.bars.duplicated(["symbol", "timestamp"]).any()
                or self.bars[["symbol", "timestamp", "available_at"]].isna().any().any()):
            raise ValueError("live bars have duplicate or missing keys")
        self.bars["timestamp"] = pd.DatetimeIndex([utc_stamp(t) for t in self.bars.timestamp])
        self.bars["available_at"] = pd.DatetimeIndex([utc_stamp(t) for t in self.bars.available_at])
        if ((self.bars.timestamp + pd.Timedelta(minutes=15) > self.bars.available_at).any()
                or (self.bars.available_at > captured).any()):
            raise ValueError("live bars were unavailable or not closed at capture")
        self.raw = require_raw_panel(pd.read_parquet(self.reference(doc["raw_bars"])), "15m")
        if "available_at" not in self.raw:
            raise ValueError("raw spot requires receipt timestamps")
        raw_at = pd.DatetimeIndex([utc_stamp(t) for t in self.raw.available_at])
        raw_close_at = pd.DatetimeIndex(self.raw.timestamp).tz_localize("UTC") + pd.Timedelta(minutes=15)
        if (raw_at > captured).any() or (raw_at < raw_close_at).any():
            raise ValueError("raw spot is future or available before bar close")
        self.surface = pd.read_parquet(self.reference(doc["surface"]))
        require_raw_surface(self.surface)
        self.context = pd.read_parquet(self.reference(doc["daily_context"]))
        for frame, kind in ((self.surface, "surface"), (self.context, "daily context")):
            if not {"date", "underlying", "available_at"} <= set(frame):
                raise ValueError(f"{kind} needs observed date and receipt provenance")
            received = pd.DatetimeIndex([utc_stamp(t) for t in frame.available_at])
            days = pd.to_datetime(frame.date, utc=True)
            if (received > captured).any() or (received < pd.DatetimeIndex(days)).any():
                raise ValueError(f"future or invalid {kind} provenance")
            if frame.duplicated(["underlying", "date"]).any():
                raise ValueError(f"duplicate {kind} keys")
        self.option_provider = SnapshotChain(pd.read_parquet(self.reference(doc["chain"])), now=captured)
        self.mapping = json.loads(self.reference(doc["condition_mapping"]).read_text())
        policy = self.expanded_inputs.document["tick_feature_policy"]
        policy_sha = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (self.mapping.get("historical_policy_sha256") != policy_sha
                or self.mapping.get("condition_namespace") != "alpaca_opra_string"
                or not self.mapping.get("allowed_trade_conditions")
                or not all(isinstance(c, str) for c in self.mapping["allowed_trade_conditions"])
                or not self.mapping.get("references")):
            raise ValueError("live condition policy needs an evidence-bound mapping to the frozen historical policy")
        for ref in self.mapping["references"]:
            self.reference(ref)
        self._ticks = {}
        self.assert_unchanged()

    def reference(self, record):
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("live snapshot references require exact path and SHA256")
        path = Path(record["path"])
        if not path.is_absolute():
            path = self.path.parent / path
        if sha256(path) != record["sha256"]:
            raise ValueError(f"live input changed: {path.name}")
        self.files[str(path)] = record["sha256"]
        return path

    def assert_unchanged(self):
        for path, digest in self.files.items():
            if sha256(path) != digest:
                raise ValueError(f"live snapshot source changed: {Path(path).name}")
        self.expanded_inputs.assert_unchanged()

    def bind_training(self, path, expected_sha256):
        """Keep the training history origin and declared feature policy fixed."""
        original = json.loads(self.reference({"path": str(path), "sha256": expected_sha256}).read_text())
        current = self.expanded_inputs.document
        for key in ("feature_contract_version", "feature_names", "selection_policy", "tick_feature_policy", "moneyness"):
            if current.get(key) != original.get(key):
                raise ValueError(f"live {key} differs from the frozen training inputs")
        if self.expanded_inputs.expected_feature_schema != original.get("feature_schema", self.expanded_inputs.expected_feature_schema):
            raise ValueError("live feature defaults differ from the training schema")
        for symbol, entry in current["symbols"].items():
            prior = original["symbols"][symbol]["context"]["dependency_metadata"]
            actual = entry["context"]["dependency_metadata"]
            for key in ("history_origin", "calendar_id", "htf_period", "vwap_anchor", "timeframe_flag_basis", "chart_session"):
                if actual.get(key) != prior.get(key):
                    raise ValueError(f"live {symbol} {key} differs from frozen training context")

    def bar_loader(self, symbol):
        group = self.bars[self.bars.symbol == symbol].sort_values("timestamp")
        bars = group.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]].copy()
        bars.index = bars.index.tz_convert("UTC").tz_localize(None)
        return self.attach(symbol, bars)

    def attach(self, symbol, bars):
        self.assert_unchanged()
        if bars_sha256(bars) != self.expanded_inputs.document["symbols"][symbol]["bars_sha256"]:
            raise ValueError("scan bars differ from the sealed full-history live context")
        return self.expanded_inputs.attach(symbol, bars)

    def candidate_kwargs(self, bars_by_symbol):
        raw = {}
        for symbol, bars in bars_by_symbol.items():
            self.attach(symbol, bars)
            frame = self.raw[self.raw.symbol == symbol]
            close = frame.set_index("timestamp").Close.sort_index()
            close.attrs = dict(self.raw.attrs, symbol=symbol)
            if len(bars.index.difference(close.index)):
                raise ValueError("live raw spot does not cover exact technical history")
            raw[symbol] = close
        return dict(expanded_inputs=self.expanded_inputs, option_provider=self.option_provider,
                    raw_close_by_symbol=raw, context=self.context.drop(columns="available_at"))

    def tick_features(self, request):
        contract = request["contract"]
        record = self.document.get("tick_windows", {}).get(request["request_id"])
        if record is None:
            raise ValueError(f"no receipt capture for selected contract {contract}; pre-subscribe before the signal window")
        coverage = json.loads(self.reference(record["coverage"]).read_text())
        start, end = request["window_start_ns"], request["window_end_ns"]
        if (coverage.get("schema") != "v6-receipt-coverage-v1" or coverage.get("contract") != contract
                or coverage.get("availability_basis") != "receipt"
                or coverage.get("status") != "reviewed_complete_capture"
                or not coverage.get("reviewed_by") or not coverage.get("references")
                or coverage.get("start_ns", end) > start or coverage.get("end_ns", start) < end
                or coverage.get("gap_count") != 0 or coverage.get("journal_errors") != 0):
            raise ValueError("receipt features require reviewed capture coverage; heartbeat alone is insufficient")
        for ref in coverage["references"]:
            self.reference(ref)
        if coverage.get("ticks_sha256") != record["ticks"]["sha256"]:
            raise ValueError("coverage report does not bind these tick bytes")
        path = self.reference(record["ticks"])
        if str(path) not in self._ticks:
            self._ticks[str(path)] = [json.loads(line) for line in path.read_text().splitlines()]
        quotes, trades = [], []
        for row in self._ticks[str(path)]:
            if (row.get("contract") != contract or row.get("condition_namespace") != "alpaca_opra_string"
                    or row.get("provider") != "alpaca" or row.get("available_at_ns") != row.get("received_at_ns")):
                raise ValueError("receipt capture identity or availability mismatch")
            if row.get("kind") not in ("quotes", "trades"):
                raise ValueError("unknown receipt tick kind")
            import msgpack
            from nn_meta.live.feeds.tick_journal import normalize_message
            raw = base64.b64decode(row["raw_msgpack_b64"], validate=True)
            if hashlib.sha256(raw).hexdigest() != row.get("raw_msgpack_sha256"):
                raise ValueError("receipt raw payload hash mismatch")
            normalized = normalize_message(msgpack.unpackb(raw, raw=False), received_at_ns=row["received_at_ns"])
            if normalized.get("normalization_error") or any(row.get(k) != v for k, v in normalized.items()):
                raise ValueError("receipt normalized fields differ from raw payload")
            (quotes if row["kind"] == "quotes" else trades).append(row)
        allowed = self.mapping["allowed_trade_conditions"]
        eligible = [r for r in trades if isinstance(r.get("conditions"), list)
                    and bool(r["conditions"]) and all(c in allowed for c in r["conditions"])]
        kwargs = dict(start_ns=start, end_ns=end, coverage_start_ns=coverage["start_ns"],
            coverage_end_ns=coverage["end_ns"], complete=True, availability="receipt",
            max_quote_age_ns=self.expanded_inputs.document["tick_feature_policy"]["max_quote_age_ns"],
            allowed_trade_conditions=allowed, allow_unconditioned_trades=False)
        reported = window_features(quotes, trades, **kwargs)
        filtered = window_features(quotes, eligible, **kwargs)
        return compute_feature_row(reported, request, eligible=filtered)

    def evidence(self):
        return {"snapshot_sha256": self.digest, "snapshot": str(self.path),
                "sources": dict(self.files), "research_only": True,
                "parity_policy": self.document["parity_policy"],
                "tick_availability": "receipt", "historical_tick_availability": "sip",
                "condition_mapping_sha256": self.document["condition_mapping"]["sha256"],
                "scanner_promotion": False}
