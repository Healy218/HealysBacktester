"""Source-default proposals for eight pinned TradingView publications.

The other five publications remain feature-only. No native footprint signal,
zone-to-trade rule, parity verdict or pool admission is invented here. Opposite
alert exits are explicit local proposal rules; source reference trade books do
not determine option fills. Frozen columns preserve source defaults and setup
priority, and require the same explicit causal context as the feature matrix.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.tradingview_features import feature_schema, validate_feature_inputs
from signals import tv_amd_po3_signals, tv_rsi_probability_signals, tv_setup_scanner_signals
from signals import tv_structure_signals, tv_trend_signals
from v3.tv_amd_po3 import AmdConfig
from v3.tv_setup_scanner import SETUPS

PROPOSAL_CONTRACT_VERSION = "2026-09-06-tv8-source-default-proposals-v1"
CONTEXT_ATTRIBUTE = "v6_tradingview_context"
SWEEP_GRIDS = {
    "tv_gaussian": {"gaussian_length": (14,), "gaussian_poles": (4,)},
    "tv_fibonacci": {"fib_midline": (200,), "fib_pivot": (7,), "fib_bandwidth": (3.0,)},
    "tv_uptrick": {"up_trend_length": (34,), "up_sensitivity": (.35,)},
    "tv_msb": {"msb_zigzag_length": (9,), "msb_fib_factor": (.33,)},
    "tv_sr": {"sr_pivot_period": (10,), "sr_channel_width": (5,)},
    "tv_rsi_probability": {"rpm_rsi": (14,), "rpm_signal": (14,), "rpm_atr_mult": (3.0,)},
    "tv_amd": {"amd_compression": (25,), "amd_fib_extension": (1.5,)},
    "tv_setup": {"setup_identity": SETUPS, "setup_stop_atr": (1.2,), "setup_max_bars": (60,)},
}
STRATEGIES = tuple(SWEEP_GRIDS)
_GRID_INPUTS = {
    "tv_gaussian": ("length", "poles"),
    "tv_fibonacci": ("midline_length", "pivot_length", "band_width"),
    "tv_uptrick": ("trend_length", "sensitivity"),
    "tv_msb": ("zigzag_length", "fib_factor"),
    "tv_sr": ("pivot_period", "channel_width_pct"),
    "tv_rsi_probability": ("rsi_period", "signal_period", "atr_multiplier"),
    "tv_amd": ("compression_percentile", "fib_extension"),
    "tv_setup": ("enabled", "stop_atr", "max_bars"),
}
SOURCE_METADATA = {
    "tv_gaussian": {"alias": "gaussian", "script_id": "AqRNdhlR", "publication_version": 1,
                    "rule": "Source directional alerts enter; opposite alert exits"},
    "tv_fibonacci": {"alias": "fibonacci", "script_id": "U7CZ8jtj", "publication_version": 1,
                     "rule": "Source continuation alerts enter; opposite trend reversal exits"},
    "tv_uptrick": {"alias": "uptrick", "script_id": "f4N0F439", "publication_version": 1,
                   "rule": "Source directional alerts enter; opposite alert exits"},
    "tv_msb": {"alias": "structure", "script_id": "DkE7UniD", "publication_version": 9,
               "rule": "Source confirmed MSB alert enters; opposite alert exits"},
    "tv_sr": {"alias": "sr", "script_id": "Ej53t8Wv", "publication_version": 6,
              "rule": "Source channel-break alert enters; opposite alert exits"},
    "tv_rsi_probability": {"alias": "probability", "script_id": "c25U5rsF", "publication_version": 1,
                           "rule": "Source accepted one-position entry; reference resolution exits"},
    "tv_amd": {"alias": "amd", "script_id": "hkKioUnL", "publication_version": 1,
               "rule": "Source distribution entry; reference target/stop/timeout exits"},
    "tv_setup": {"alias": "setup", "script_id": "XWuYNmhD", "publication_version": 2,
                 "rule": "Per-identity accepted source entry and reference resolution exit; all six identities remain enabled in source priority"},
}
REQUIRED_OUTPUT_EVENTS = {
    "AqRNdhlR": ("bull_signal", "bear_signal"),
    "U7CZ8jtj": ("bull_signal", "bear_signal", "bull_flip", "bear_flip"),
    "f4N0F439": ("bull_signal", "bear_signal"),
    "DkE7UniD": ("bull_signal", "bear_signal"),
    "Ej53t8Wv": ("bull_signal", "bear_signal"),
    "c25U5rsF": ("long_entry", "long_exit", "short_entry", "short_exit"),
    "hkKioUnL": ("long_entry", "long_exit", "short_entry", "short_exit"),
    "XWuYNmhD": tuple(f"{name}_{field}" for name in SETUPS
                       for field in ("long_entry", "long_exit", "short_entry", "short_exit")),
}
FIXED_INPUTS_METADATA = {
    "numerical_settings": "Pinned adaptation-manifest defaults only; no optimization alternatives",
    "required_context": ("minimum_tick", "timeframe_flags", "dependency_metadata", "as_of", "session_policy"),
    "optional_context": ("vwap_observations",),
    "context_schema": "nn_meta.tradingview_features.feature_requirements()",
    "context_attribute": CONTEXT_ATTRIBUTE,
    "prefix_rule": "Exact prefix of context; fixed history_origin; as_of capped at final prefix close",
    "setup_book": "All six source identities enabled, default max_open=1 and priority; column selection does not disable other identities",
    "availability": "Completed bar close; never pivot/drawing origin backdating",
    "external_parity": False, "active_pool_admission": False,
}


def registry_metadata(*, minimum_tick, session_policy, vwap_mode="reset_flags"):
    """Export exact source/default/input declarations for freeze/fixture gates."""
    schema = feature_schema(minimum_tick=minimum_tick, session_policy=session_policy, vwap_mode=vwap_mode)
    for strategy, source in SOURCE_METADATA.items():
        _check_default_grid(strategy, schema["parameters"][source["alias"]])
    return {"contract_version": PROPOSAL_CONTRACT_VERSION, "strategies": list(STRATEGIES),
            "grids": deepcopy(SWEEP_GRIDS), "sources": deepcopy(SOURCE_METADATA),
            "required_source_event_fields": deepcopy(REQUIRED_OUTPUT_EVENTS),
            "wrapper_runtime": _wrapper_runtime(),
            "fixed_inputs": deepcopy(FIXED_INPUTS_METADATA),
            "parameters": {s: schema["parameters"][r["alias"]] for s, r in SOURCE_METADATA.items()},
            "runtime_parameter_bindings": schema["runtime_parameter_bindings"],
            "external_parity": False, "active_pool_admission": False}


def _wrapper_runtime():
    """Bind the exact signal adapters as well as numerical source-port identity."""
    functions = {
        "tv_gaussian": tv_trend_signals.generate_gaussian_filter_signals,
        "tv_fibonacci": tv_trend_signals.generate_fibonacci_trend_signals,
        "tv_uptrick": tv_trend_signals.generate_uptrick_trend_signals,
        "tv_msb": tv_structure_signals.generate_market_structure_signals,
        "tv_sr": tv_structure_signals.generate_sr_channel_signals,
        "tv_rsi_probability": tv_rsi_probability_signals.generate_rsi_probability_signals,
        "tv_amd": tv_amd_po3_signals.generate_amd_po3_signals,
        "tv_setup": tv_setup_scanner_signals.generate_setup_scanner_signals,
    }
    root, bindings = Path(__file__).resolve().parents[1], {}
    for strategy, function in functions.items():
        source = inspect.getsourcefile(function)
        if source is None:
            raise ValueError("proposal wrapper requires an inspectable source module")
        path = Path(source).absolute()
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("proposal wrapper source cannot contain symlinks")
        before = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError("proposal wrapper source changed during registry binding")
        bindings[strategy] = {"module": function.__module__, "function": function.__qualname__,
            "source_file": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            "sha256": digest}
    return bindings


def _check_default_grid(strategy, parameters):
    defaults = parameters["config"] if strategy == "tv_amd" else parameters
    grid = SWEEP_GRIDS[strategy]
    if len(grid) != len(_GRID_INPUTS[strategy]):
        raise ValueError("TradingView proposal grid differs from source defaults")
    for name, input_name in zip(grid, _GRID_INPUTS[strategy]):
        expected = tuple(defaults[input_name]) if name == "setup_identity" else (defaults[input_name],)
        if tuple(grid[name]) != expected:
            raise ValueError(f"{name} grid differs from source defaults; unverified optimization is unsupported")


def _context_for_prefix(bars, context):
    if not isinstance(context, dict):
        raise ValueError(f"explicit {CONTEXT_ATTRIBUTE} context is required")
    required = set(FIXED_INPUTS_METADATA["required_context"])
    if not required.issubset(context) or set(context) - required - {"vwap_observations"}:
        raise ValueError("proposal context must use the exact declared feature-context schema")
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise ValueError("proposal bars must be a nonempty completed history prefix")
    flags = context["timeframe_flags"]
    if (not isinstance(flags, pd.DataFrame) or not flags.index.is_unique
            or not flags.index.is_monotonic_increasing
            or not bars.index.equals(flags.index[:len(bars)])):
        raise ValueError("proposal bars must be an exact prefix of the declared context history")
    prepared = {key: deepcopy(value) for key, value in context.items()
                if key not in ("timeframe_flags", "vwap_observations")}
    prepared["timeframe_flags"] = flags.iloc[:len(bars)].copy(deep=True)
    observed = context.get("vwap_observations")
    if observed is not None:
        if not isinstance(observed, pd.DataFrame) or not observed.index.equals(flags.index):
            raise ValueError("VWAP observations must share the full context history index")
        prepared["vwap_observations"] = observed.iloc[:len(bars)].copy(deep=True)
    declared = pd.Timestamp(prepared["as_of"])
    if pd.isna(declared) or declared.tz is None:
        raise ValueError("proposal as_of must be an explicit nonmissing aware time")
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("proposal bar opens must be timezone-aware")
    prepared["as_of"] = min(declared, bars.index[-1] + pd.Timedelta(minutes=15))
    # Context DataFrames in attrs are not indicator inputs. Clear only this
    # detached copy, avoiding pandas' ambiguous attrs equality during concat.
    clean = bars.copy(deep=True)
    clean.attrs = {}
    validate_feature_inputs(clean, **prepared)
    return clean, prepared


def _default_inputs(strategy, context):
    schema = feature_schema(minimum_tick=context["minimum_tick"], session_policy=context["session_policy"],
                            vwap_mode="observed" if context.get("vwap_observations") is not None else "reset_flags")
    fixed = deepcopy(schema["parameters"][SOURCE_METADATA[strategy]["alias"]])
    _check_default_grid(strategy, fixed)
    if "as_of" in fixed:
        fixed["as_of"] = context["as_of"]
    return fixed


def sweep_signals(strategy, bars, *, context, enable_shorting=False):
    """Singleton default grids; Setup has six source-identity columns."""
    if strategy not in STRATEGIES:
        raise ValueError(f"not a directional TradingView proposal: {strategy}")
    if not isinstance(enable_shorting, bool):
        raise ValueError("enable_shorting must be boolean")
    clean, selected = _context_for_prefix(bars, context)
    p = _default_inputs(strategy, selected)
    g = SWEEP_GRIDS[strategy]
    if strategy == "tv_gaussian":
        p.pop("length")
        p.pop("poles")
        frames = tv_trend_signals.generate_gaussian_filter_signals(clean, g["gaussian_length"], g["gaussian_poles"], enable_shorting=enable_shorting, **p)
    elif strategy == "tv_fibonacci":
        for key in ("midline_length", "pivot_length", "band_width"):
            p.pop(key)
        frames = tv_trend_signals.generate_fibonacci_trend_signals(clean, g["fib_midline"], g["fib_pivot"], g["fib_bandwidth"], enable_shorting=enable_shorting, **p)
    elif strategy == "tv_uptrick":
        p.pop("trend_length")
        p.pop("sensitivity")
        frames = tv_trend_signals.generate_uptrick_trend_signals(clean, g["up_trend_length"], g["up_sensitivity"], enable_shorting=enable_shorting, **p)
    elif strategy == "tv_msb":
        frames = tv_structure_signals.generate_market_structure_signals(clean, g["msb_zigzag_length"], g["msb_fib_factor"], enable_shorting=enable_shorting)
    elif strategy == "tv_sr":
        p.pop("pivot_period")
        p.pop("channel_width_pct")
        frames = tv_structure_signals.generate_sr_channel_signals(clean, g["sr_pivot_period"], g["sr_channel_width"], enable_shorting=enable_shorting, **p)
    elif strategy == "tv_rsi_probability":
        for key in ("rsi_period", "signal_period", "atr_multiplier"):
            p.pop(key)
        frames = tv_rsi_probability_signals.generate_rsi_probability_signals(clean, g["rpm_rsi"], g["rpm_signal"], g["rpm_atr_mult"], enable_shorting=enable_shorting, **p)
    elif strategy == "tv_amd":
        p["config"] = AmdConfig(**p["config"])
        frames = tv_amd_po3_signals.generate_amd_po3_signals(clean, g["amd_compression"], g["amd_fib_extension"], enable_shorting=enable_shorting, **p)
    else:
        p.pop("stop_atr")
        p.pop("max_bars")
        if selected.get("vwap_observations") is not None:
            p["vwap_observations"] = selected["vwap_observations"]
        else:
            p["vwap_reset"] = selected["timeframe_flags"].vwap_reset
        frames = tv_setup_scanner_signals.generate_setup_scanner_signals(clean, g["setup_stop_atr"], g["setup_max_bars"], setup_names=g["setup_identity"], enable_shorting=enable_shorting, **p)
    for frame in frames:
        if frame is not None:
            if not frame.index.equals(clean.index) or any(not pd.api.types.is_bool_dtype(frame[c]) for c in frame):
                raise ValueError("proposal wrapper changed index or event types")
            frame.attrs["tradingview_proposal"] = {
                "contract_version": PROPOSAL_CONTRACT_VERSION, "strategy": strategy,
                "source": deepcopy(SOURCE_METADATA[strategy]),
                "history_origin": selected["dependency_metadata"]["history_origin"],
                "as_of": selected["as_of"].isoformat(), "session_policy": selected["session_policy"],
                "available_at_basis": "bar_open + 15 minutes",
                "external_parity": False, "active_pool_admission": False,
            }
    return frames


def single_signals(strategy, bars, params, *, context, enable_shorting=False):
    """Replay exactly one declared default column, retaining the full source book."""
    if strategy not in STRATEGIES:
        raise ValueError(f"not a directional TradingView proposal: {strategy}")
    grid = SWEEP_GRIDS[strategy]
    if not isinstance(params, dict) or set(params) != set(grid):
        raise ValueError("frozen TradingView parameters must match the declared grid fields")
    for name, choices in grid.items():
        value = params[name]
        if isinstance(choices[0], str):
            valid = isinstance(value, str) and value in choices
        else:
            valid = isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and np.isfinite(value) and value in choices
        if not valid:
            raise ValueError(f"{name} is not a declared source-default grid value")
    frames = sweep_signals(strategy, bars, context=context, enable_shorting=enable_shorting)
    column = tuple(params[name] for name in grid)
    return tuple(frame[[column]] if frame is not None else None for frame in frames)
