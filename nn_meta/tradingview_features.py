"""Experimental, causal feature projection of all thirteen pinned TV ports.

This module makes no external parity or model-admission claim. Source licenses
remain attached to the underlying adaptations. No trade direction is invented
for a feature-only publication. See docs/specs/V6_TRADINGVIEW_FEATURES.md.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

from indicators.tradingview_registry import build_catalog
from v3._tv_profile_support import profile_observations
from v3._tv_setup_support import aligned_observations
from v3._tv_trend_support import pine_ohlc, positive
from v3.pine_compat import atr
from v3.tv_amd_po3 import AmdConfig, amd_po3
from v3.tv_fibonacci import fibonacci_trend_continuation
from v3.tv_gaussian import gaussian_filter_trend
from v3.tv_htf_log_profile import htf_log_regression_profile
from v3.tv_ict_killzones import DEFAULT_SESSIONS, SessionWindow, ict_killzones
from v3.tv_liquidity_poc import structural_liquidity_poc
from v3.tv_market_structure import market_structure_break
from v3.tv_rsi_probability import rsi_probability_matrix
from v3.tv_setup_scanner import SETUPS, setup_scanner
from v3.tv_sr_channels import support_resistance_channels
from v3.tv_uptrick import uptrick_adaptive_trend
from v3.tv_volume_footprint import volume_footprint
from v3.tv_volume_order_blocks import volume_order_blocks

ROOT = Path(__file__).resolve().parents[1]
FEATURE_CONTRACT_VERSION = "2026-09-06-tv13-features-v1"
BAR_MINUTES = 15
SOURCE_MAP = (
    ("gaussian", "AqRNdhlR", gaussian_filter_trend),
    ("fibonacci", "U7CZ8jtj", fibonacci_trend_continuation),
    ("uptrick", "f4N0F439", uptrick_adaptive_trend),
    ("structure", "DkE7UniD", market_structure_break),
    ("sr", "Ej53t8Wv", support_resistance_channels),
    ("probability", "c25U5rsF", rsi_probability_matrix),
    ("ict", "nW5oGfdO", ict_killzones),
    ("order_blocks", "KcnNgwDI", volume_order_blocks),
    ("amd", "hkKioUnL", amd_po3),
    ("setup", "XWuYNmhD", setup_scanner),
    ("liquidity", "I8HrQVRv", structural_liquidity_poc),
    ("htf", "kwXpL7yZ", htf_log_regression_profile),
    ("footprint", "Tm1cGCPD", volume_footprint),
)


@dataclass(frozen=True)
class FeatureSpec:
    source: str
    field: str
    transform: str = "value"
    valid_when: str | None = None

    @property
    def name(self):
        suffix = {"price_atr": "_distance_atr14", "range_atr": "_atr14",
                  "percent": "_fraction"}.get(self.transform, "")
        return f"tv_{self.source}_{self.field}{suffix}"


def _specs(source, fields, transform="value", valid_when=None):
    return tuple(FeatureSpec(source, field, transform, valid_when) for field in fields)


# Order is part of the feature contract. Every numeric projection is explicit;
# no discovery of newly added port columns can silently change a model schema.
FEATURE_SPECS = (
    *_specs("gaussian", ("direction", "smoothed_efficiency")),
    *_specs("gaussian", ("bull_signal", "bear_signal"), "event"),
    *_specs("gaussian", ("trend_line",), "price_atr"),
    *_specs("gaussian", ("trend_width",), "range_atr"),
    *_specs("fibonacci", ("direction",)),
    *_specs("fibonacci", ("bull_signal", "bear_signal", "trend_flip"), "event"),
    *_specs("fibonacci", ("midline",), "price_atr"),
    *_specs("fibonacci", ("volatility",), "range_atr"),
    *_specs("uptrick", ("direction", "regime")),
    *_specs("uptrick", ("bull_signal", "bear_signal"), "event"),
    *_specs("uptrick", ("inner_trail",), "price_atr"),
    *_specs("structure", ("market_direction",)),
    *_specs("structure", ("bull_signal", "bear_signal"), "event"),
    *_specs("structure", ("high_0", "low_0"), "price_atr"),
    *_specs("sr", ("inside_channel", "bull_signal", "bear_signal"), "event"),
    *_specs("sr", ("channel_1_top", "channel_1_bottom"), "price_atr"),
    *_specs("sr", ("channel_1_strength",)),
    *_specs("probability", ("rsi",), "percent"),
    *_specs("probability", ("raw_long_signal", "raw_short_signal"), "event"),
    *_specs("probability", ("active_side", "resolved_total")),
    *_specs("probability", ("long_reference_win_pct", "short_reference_win_pct"), "percent"),
    *(spec for session in DEFAULT_SESSIONS for spec in (
        *_specs("ict", (f"{session}_in_session", f"{session}_break_high", f"{session}_break_low"), "event"),
        *_specs("ict", (f"{session}_range_value",), "range_atr"),
    )),
    *_specs("order_blocks", ("bull_active_count", "bear_active_count")),
    *_specs("order_blocks", ("bull_retest", "bear_retest"), "event"),
    *_specs("order_blocks", ("bull_latest_trigger", "bear_latest_trigger"), "price_atr"),
    *_specs("amd", ("phase",), "phase"),
    *_specs("amd", ("long_entry", "short_entry"), "event"),
    *_specs("amd", ("compression_rank",), "percent"),
    *_specs("amd", ("range_width",), "range_atr"),
    *_specs("amd", ("all_closed",)),
    *(spec for setup in SETUPS for spec in _specs("setup", (f"{setup}_raw_long", f"{setup}_raw_short"), "event")),
    *_specs("setup", ("vwap",), "price_atr"),
    *_specs("setup", ("or_done", "session_gap"), "event"),
    *_specs("liquidity", ("top_sweep", "bottom_sweep", "profile_ready"), "event"),
    *_specs("liquidity", ("poc_price",), "price_atr", "profile_ready"),
    *_specs("liquidity", ("liquidity_top", "liquidity_bottom"), "price_atr"),
    *_specs("htf", ("regression_slope",)),
    *_specs("htf", ("delta_pct",), "percent"),
    *_specs("htf", ("regression_end",), "price_atr"),
    *_specs("htf", ("poc_end",), "price_atr", "profile_ready"),
    *_specs("htf", ("completed_poc_end",), "price_atr", "completed_profile_ready"),
    *_specs("htf", ("profile_ready", "completed_profile_ready"), "event"),
    *_specs("footprint", ("buy_share_pct", "profile_tilt_pct"), "percent"),
    *_specs("footprint", ("chart_poc",), "price_atr", "chart_poc_fresh"),
    *_specs("footprint", ("chart_poc_fresh",), "event"),
    *_specs("footprint", ("window_bars",)),
)
FEATURE_NAMES = tuple(spec.name for spec in FEATURE_SPECS)
PHASE_CODES = {"idle": 0, "accum": 1, "sweepPending": 2, "manip": 3, "dist": 4}


@dataclass(frozen=True)
class TradingViewFeatureMatrix:
    values: pd.DataFrame
    available_at: pd.Series
    metadata: dict


def feature_requirements() -> dict:
    """Preflight requirements; declarations are not calendar/parity evidence."""
    return {
        "contract_version": FEATURE_CONTRACT_VERSION,
        "columns": list(FEATURE_NAMES), "source_count": len(SOURCE_MAP),
        "bars": "Nonempty finite OHLCV, positive Close, nonnegative Volume, timezone-aware 15m bar-open index; fixed history origin",
        "minimum_tick": "Explicit positive instrument syminfo.mintick",
        "as_of": "Explicit timezone-aware time at or after every supplied bar close",
        "timeframe_flags": {"vwap_reset": "Exact exchange/TradingView VWAP anchor boolean; omit only when exact vwap_observations supplied",
                            "htf_change": "Exact Pine timeframe.change('2D') boolean for a 15m chart",
                            "available_at": "Nonmissing aware timestamp no later than the matching bar open"},
        "dependency_metadata": ["symbol", "calendar_id", "htf_period", "vwap_anchor", "timeframe_flag_basis", "chart_session", "history_origin"],
        "vwap_observations": "Optional alternative to reset flags: exact aligned vwap and available_at columns; observed no later than bar close; no implied daily-reset equivalence",
        "session_policies": {"strict": "Reject gaps concealing a Setup ORB session reset",
                             "source_literal": "Preserve upstream membership transitions across RTH-only days; expose session_gap; no invented reset"},
        "unsupported": ["native/intrabar footprint", "inferred 2D grouping", "inferred VWAP reset",
                        "external-source Gaussian input", "chart-object backfills", "truncated/rebased history"],
        "external_parity": False, "model_admission": False,
    }


def _gaps(index, session):
    # Every source wrapper validates the same full-history index. Cache only
    # this pure calendar computation, never prices or feature values. Return
    # a detached array so a caller cannot mutate another validation result.
    values = _cached_gaps(index.as_unit("ns").asi8.tobytes(), session)
    return pd.Series(values.copy(), index=index, dtype=bool)


from functools import lru_cache


@lru_cache(maxsize=32)
def _cached_gaps(stamps, session):
    index = pd.DatetimeIndex(np.frombuffer(stamps, dtype=np.int64), tz="UTC")
    window = SessionWindow.parse(session)
    local = index.tz_convert("America/New_York")
    previous_inside, previous_instance = False, None
    gaps = []
    for stamp in local:
        inside, instance = window.locate(stamp)
        gaps.append(bool(inside and previous_inside and instance != previous_instance))
        previous_inside, previous_instance = inside, instance
    return np.asarray(gaps, dtype=bool)


def validate_feature_inputs(bars, *, minimum_tick, timeframe_flags,
                            dependency_metadata, as_of, session_policy="strict",
                            vwap_observations=None) -> dict:
    """Validate required context before expensive ports; raise on missing data.

    The metadata is caller provenance, not proof that flags reproduce Pine.
    No calendar grouping, missing bar or intrabar stream is synthesized here.
    """
    if not isinstance(bars, pd.DataFrame) or bars.empty or not bars.columns.is_unique:
        raise ValueError("bars must be a nonempty DataFrame with unique columns")
    available = profile_observations(bars, BAR_MINUTES, as_of, logarithmic=True)
    if as_of is None or pd.isna(pd.Timestamp(as_of)):
        raise ValueError("as_of is required and cannot be NaT")
    if ((bars.index.as_unit("ns").asi8 % pd.Timedelta(minutes=BAR_MINUTES).value) != 0).any():
        raise ValueError("bar opens must align to the 15m grid")
    positive("minimum_tick", minimum_tick)
    if isinstance(minimum_tick, (bool, np.bool_)):
        raise ValueError("minimum_tick must be numeric, not boolean")
    if session_policy not in ("strict", "source_literal", "local_research"):
        raise ValueError("session_policy must be strict, source_literal or local_research")
    flag_columns = {"htf_change", "available_at"} | ({"vwap_reset"} if vwap_observations is None else set())
    if (not isinstance(timeframe_flags, pd.DataFrame) or not timeframe_flags.index.equals(bars.index)
            or not timeframe_flags.columns.is_unique
            or set(timeframe_flags) != flag_columns):
        raise ValueError("timeframe_flags must align exactly with htf_change, available_at, and vwap_reset only when no observed VWAP is supplied")
    for column in flag_columns - {"available_at"}:
        if not pd.api.types.is_bool_dtype(timeframe_flags[column]) or timeframe_flags[column].isna().any():
            raise ValueError(f"{column} must be nonmissing boolean flags")
    at = timeframe_flags.available_at
    if not isinstance(at.dtype, pd.DatetimeTZDtype) or at.isna().any():
        raise ValueError("timeframe flag available_at must be nonmissing timezone-aware timestamps")
    if (at > pd.Series(bars.index, index=bars.index)).any():
        raise ValueError("timeframe flags were unavailable at their bar open")
    if vwap_observations is not None:
        if (not isinstance(vwap_observations, pd.DataFrame) or not vwap_observations.columns.is_unique
                or set(vwap_observations) != {"vwap", "available_at"}):
            raise ValueError("vwap_observations require exactly vwap and available_at columns")
        aligned_observations(vwap_observations, bars.index, available, ["vwap"])
        if (vwap_observations.vwap.dropna() <= 0).any():
            raise ValueError("observed VWAP must be positive or NaN")
    if not isinstance(dependency_metadata, dict) or any(
        not isinstance(dependency_metadata.get(key), str) or not dependency_metadata[key].strip()
        for key in feature_requirements()["dependency_metadata"]
    ):
        raise ValueError("dependency_metadata must declare all required nonempty provenance strings")
    if dependency_metadata["htf_period"] != "2D":
        raise ValueError("source-default 15m HTF period must be exactly 2D")
    try:
        origin = pd.Timestamp(dependency_metadata["history_origin"])
    except (TypeError, ValueError) as exc:
        raise ValueError("history_origin must declare the fixed first bar") from exc
    if pd.isna(origin) or origin.tz is None or origin != bars.index[0]:
        raise ValueError("history_origin differs from the supplied first bar; rebasing is unsupported")
    try:
        json.dumps(dependency_metadata, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("dependency_metadata must be finite JSON provenance") from exc
    session_gaps = _gaps(bars.index, "0930-1600")
    if session_policy == "strict" and session_gaps.any():
        raise ValueError("missing outside-session bars conceal Setup ORB reset; explicitly select source_literal for matching RTH chart semantics")
    ict_gaps = {name: int(_gaps(bars.index, session).sum()) for name, session in DEFAULT_SESSIONS.items()}
    for name, count in ict_gaps.items():
        if count and session_policy != "local_research":
            raise ValueError(f"missing outside-session bars conceal ICT {name} reset; unsupported input coverage")
    return {"dependencies_validated": True, "bar_count": len(bars),
            "available_at": available, "setup_session_gap_count": int(session_gaps.sum()),
            "ict_session_gap_count": ict_gaps,
            "session_policy": session_policy, "external_context_verified": False,
            "vwap_mode": "observed" if vwap_observations is not None else "reset_flags"}


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _settings(catalog, minimum_tick, session_policy):
    records = {record["script_id"]: record for record in catalog["scripts"]}
    if set(records) != {script_id for _, script_id, _ in SOURCE_MAP}:
        raise ValueError("feature sources differ from the thirteen-publication registry")
    settings = {}
    for alias, script_id, _ in SOURCE_MAP:
        record = records[script_id]
        manifest = json.loads((ROOT / record["adaptation_manifest"]).read_text())
        declaration = next(item for item in manifest["scripts"] if item["public_id"] == script_id)
        parameters = deepcopy(declaration["defaults"])
        if alias in ("uptrick", "ict"):
            parameters["minimum_tick"] = float(minimum_tick)
        if alias == "ict" and session_policy == "local_research":
            parameters["strict_session_coverage"] = False
        if alias == "amd":
            parameters["config"]["minimum_tick"] = float(minimum_tick)
        if alias == "setup":
            parameters["strict_session_coverage"] = session_policy == "strict"
        if alias == "footprint":
            parameters.update(tick_size=float(minimum_tick), engine="geometric", include_diagnostics=False)
        settings[alias] = parameters
    return settings


def feature_schema(*, minimum_tick, session_policy="strict", vwap_mode="reset_flags") -> dict:
    """Return the fixed columns and pinned defaults for fixture/preflight work."""
    positive("minimum_tick", minimum_tick)
    if isinstance(minimum_tick, (bool, np.bool_)):
        raise ValueError("minimum_tick must not be boolean")
    if session_policy not in ("strict", "source_literal", "local_research"):
        raise ValueError("unknown session policy")
    if vwap_mode not in ("reset_flags", "observed"):
        raise ValueError("vwap_mode must be reset_flags or observed")
    catalog = build_catalog(ROOT)
    return {"contract_version": FEATURE_CONTRACT_VERSION,
            "parameters": _settings(catalog, minimum_tick, session_policy),
            "columns": [{"name": s.name, "source": s.source, "field": s.field,
                         "transform": s.transform, "valid_when": s.valid_when} for s in FEATURE_SPECS],
            "sources": {alias: script_id for alias, script_id, _ in SOURCE_MAP},
            "runtime_parameter_bindings": {("setup.vwap_reset" if vwap_mode == "reset_flags" else "setup.vwap_observations"): ("timeframe_flags.vwap_reset" if vwap_mode == "reset_flags" else "vwap_observations"),
                                           "htf.htf_change": "timeframe_flags.htf_change (2D)",
                                           "supported_ports.as_of": "explicit as_of argument"},
            "external_parity": False, "model_admission": False}


def tradingview_features(bars, *, minimum_tick, timeframe_flags,
                        dependency_metadata, as_of, session_policy="strict",
                        vwap_observations=None, observation_index=None) -> TradingViewFeatureMatrix:
    """Project every port with fixed defaults; all rows become known at close.

    ``price_atr`` = (source level - current Close) / completed-bar Pine ATR14.
    Warmup/absent values remain NaN. No imputation, clipping, rolling rescaling,
    historical signal shift, model admission or trade-policy mapping occurs.
    """
    # Snapshot caller-owned values so the bound input bytes are the values used.
    bars = bars.copy(deep=True) if isinstance(bars, pd.DataFrame) else bars
    timeframe_flags = timeframe_flags.copy(deep=True) if isinstance(timeframe_flags, pd.DataFrame) else timeframe_flags
    vwap_observations = vwap_observations.copy(deep=True) if isinstance(vwap_observations, pd.DataFrame) else vwap_observations
    dependency_metadata = deepcopy(dependency_metadata)
    projection_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    context = validate_feature_inputs(bars, minimum_tick=minimum_tick, timeframe_flags=timeframe_flags,
                                      dependency_metadata=dependency_metadata, as_of=as_of,
                                      session_policy=session_policy, vwap_observations=vwap_observations)
    projected_index = bars.index if observation_index is None else pd.DatetimeIndex(observation_index)
    if (not len(projected_index) or not projected_index.is_unique or not projected_index.is_monotonic_increasing
            or len(projected_index.difference(bars.index))):
        raise ValueError("feature observations must be distinct ordered original-history bars")
    catalog = build_catalog(ROOT)
    settings = _settings(catalog, minimum_tick, session_policy)
    frames, timings = {}, {}
    for alias, _, calculator in SOURCE_MAP:
        kwargs = deepcopy(settings[alias])
        if "as_of" in kwargs:
            kwargs["as_of"] = as_of
        if alias == "amd":
            kwargs["config"] = AmdConfig(**kwargs["config"])
        if alias == "setup":
            if vwap_observations is None:
                kwargs["vwap_reset"] = timeframe_flags.vwap_reset
            else:
                kwargs["vwap_observations"] = vwap_observations
        if alias == "htf":
            flags = timeframe_flags.htf_change.copy()
            flags.attrs["htf_period"] = "2D"
            kwargs["htf_change"] = flags
        if alias in ("footprint", "htf") and observation_index is not None:
            kwargs["observation_positions"] = [int(i) for i in bars.index.get_indexer(projected_index)]
        started = time.perf_counter()
        frames[alias] = calculator(bars, **kwargs)
        timings[alias] = time.perf_counter() - started
        expected_index = projected_index if alias in ("footprint", "htf") and observation_index is not None else bars.index
        if not frames[alias].index.equals(expected_index):
            raise ValueError(f"{alias} changed feature observation index")
        expected_at = pd.DatetimeIndex(pd.Series(context["available_at"], index=bars.index).loc[expected_index])
        if "available_at" in frames[alias] and not pd.DatetimeIndex(frames[alias].available_at).equals(expected_at):
            raise ValueError(f"{alias} changed completed-bar availability")
        frames[alias] = frames[alias].loc[projected_index]
    scale = atr(pine_ohlc(bars), 14)
    scale = scale.where(scale > 0)
    scale = scale.loc[projected_index]
    projected_close = bars.Close.loc[projected_index]
    columns = {}
    for spec in FEATURE_SPECS:
        frame = frames[spec.source]
        raw = frame[spec.field]
        if spec.transform == "phase":
            if not raw.isin(PHASE_CODES).all():
                raise ValueError("unrecognized AMD source phase")
            value = raw.map(PHASE_CODES).astype(float)
        else:
            if spec.transform == "event" and (not pd.api.types.is_bool_dtype(raw) or raw.isna().any()):
                raise ValueError(f"{spec.name} must be an exact source boolean")
            value = raw.astype(float)
            if spec.transform == "price_atr":
                value = (value - projected_close) / scale
            elif spec.transform == "range_atr":
                value = value / scale
            elif spec.transform == "percent":
                value = value / 100.
        if spec.valid_when:
            value = value.where(frame[spec.valid_when])
        # Zero prior samples are unknown reference rates, not evidence of 0%.
        if spec.source == "probability" and spec.field.endswith("reference_win_pct"):
            side = spec.field.split("_", 1)[0]
            value = value.where(frame[f"total_{side}_wins"] + frame[f"total_{side}_losses"] > 0)
        columns[spec.name] = value
    matrix = pd.DataFrame(columns, index=projected_index, dtype=float)
    if tuple(matrix.columns) != FEATURE_NAMES or np.isinf(matrix.to_numpy()).any():
        raise ValueError("invalid feature schema or nonfinite normalization")
    after = build_catalog(ROOT)
    identities = {row["script_id"]: row["fixture_identity_sha256"] for row in catalog["scripts"]}
    if identities != {row["script_id"]: row["fixture_identity_sha256"] for row in after["scripts"]}:
        raise ValueError("source/runtime identity changed during feature calculation")
    if projection_sha256 != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("feature projection changed during calculation")
    boolean_columns = sorted(set(timeframe_flags) - {"available_at"})
    flags_bytes = (json.dumps(boolean_columns).encode() + timeframe_flags[boolean_columns].to_numpy(dtype=np.uint8).tobytes()
                   + pd.DatetimeIndex(timeframe_flags.available_at).as_unit("ns").asi8.astype("<i8").tobytes())
    vwap_hash = None
    if vwap_observations is not None:
        vwap_hash = hashlib.sha256(vwap_observations.vwap.to_numpy(dtype="<f8").tobytes()
                                  + pd.DatetimeIndex(vwap_observations.available_at).as_unit("ns").asi8.astype("<i8").tobytes()).hexdigest()
    input_bytes = (bars.index.as_unit("ns").asi8.astype("<i8").tobytes()
                   + bars[["Open", "High", "Low", "Close", "Volume"]].to_numpy(dtype="<f8").tobytes())
    metadata_out = {
        "contract_version": FEATURE_CONTRACT_VERSION, "source_count": len(SOURCE_MAP),
        "source_fixture_identities": identities, "source_ids": {a: s for a, s, _ in SOURCE_MAP},
        "fixed_parameters": settings, "column_names": list(FEATURE_NAMES),
        "projection_sha256": projection_sha256,
        "runtime_parameter_bindings": {("setup.vwap_reset" if vwap_observations is None else "setup.vwap_observations"): ("timeframe_flags.vwap_reset" if vwap_observations is None else "vwap_observations"),
                                       "htf.htf_change": "timeframe_flags.htf_change (2D)",
                                       "supported_ports.as_of": "explicit as_of argument"},
        "bar_input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "timeframe_flags_sha256": hashlib.sha256(flags_bytes).hexdigest(),
        "vwap_observations_sha256": vwap_hash, "vwap_mode": context["vwap_mode"],
        "dependency_metadata": deepcopy(dependency_metadata), "session_policy": session_policy,
        "setup_session_gap_count": context["setup_session_gap_count"],
        "history_origin": bars.index[0].isoformat(), "last_bar_open": bars.index[-1].isoformat(),
        "as_of": pd.Timestamp(as_of).isoformat(), "index_kind": "bar_open",
        "available_at_basis": "bar_open + 15 minutes; no retrospective assignment",
        "normalization": "(level-Close)/Pine ATR14; ranges/ATR14; percentages/100; NaN retained",
        "footprint_scope": "modeled geometric allocation; default table/chart metrics; unused Simpson/overlap diagnostics disabled",
        "external_context_verified": False, "external_parity": False, "model_admission": False,
        "runtime": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__},
        "nonmissing_counts": {name: int(matrix[name].notna().sum()) for name in matrix},
        "timings_seconds": timings,
    }
    metadata_out["configuration_sha256"] = _canonical({
        "contract": FEATURE_CONTRACT_VERSION, "parameters": settings, "identities": identities,
        "projection": metadata_out["projection_sha256"], "dependency_metadata": dependency_metadata,
        "vwap_mode": context["vwap_mode"],
        "runtime": metadata_out["runtime"],
    })
    metadata_out["projected_observation_count"] = len(projected_index)
    return TradingViewFeatureMatrix(matrix, pd.Series(context["available_at"], index=bars.index, name="available_at").loc[projected_index], metadata_out)
