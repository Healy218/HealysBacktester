"""Feature-timing contract for the v4 causal meta-labeling pipeline.

The legacy meta dataset stores features and realized option labels in one
row.  That makes it easy to accidentally promote a value observed at the
option fill into a model input.  V4 keeps a small, explicit registry of each
feature's latest availability.  A feature is eligible for a signal-close
decision only when its availability is no later than ``SIGNAL_CLOSE``.

This module deliberately does not change ``META_FEATURES``. Column names do
not establish compatibility: default loaders reject bundles without the current
feature-contract tag. ``v4_feature_names`` is the schema new v4 runs must use.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Mapping

CONTRACT_VERSION = "2026-09-05-causal-v2"


def baseline_spec_fingerprint(spec: dict) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require_current_dataset(rows, spec: dict | None = None) -> None:
    """Refuse pre-audit features/labels; column names alone cannot prove causality."""
    if rows.attrs.get("feature_contract_version") != CONTRACT_VERSION:
        raise FeatureAvailabilityError(
            "dataset uses an absent/stale feature contract; rebuild freeze, rows and marks")
    if spec is not None and rows.attrs.get("baseline_spec_sha256") != baseline_spec_fingerprint(spec):
        raise FeatureAvailabilityError("dataset baseline fingerprint differs; rebuild rows from this exact spec")


class Availability(IntEnum):
    """Latest point at which a value can first be known for one proposal."""

    PREVIOUS_SESSION_CLOSE = 0
    SIGNAL_CLOSE = 1
    NEXT_OPTION_OPEN = 2
    EXIT_CLOSE = 3


@dataclass(frozen=True)
class FeatureSpec:
    """Provenance and latest availability for one model feature."""

    name: str
    available_at: Availability
    source: str
    rationale: str


class FeatureAvailabilityError(ValueError):
    """Raised when a requested model schema contains a post-decision value."""


_TECHNICAL = (
    "ma_gap", "px_vs_fast", "rsi14", "macd_hist", "bb_z", "ret_1",
    "ret_8", "ret_26", "session_gap", "gap_abs_z", "tod", "dow",
    "is_first_hour", "is_last_hour", "dow_tod",
)
_SURFACE = (
    "rvol_5", "rvol_21", "atm_iv_near", "atm_iv_far", "term_slope",
    "iv_chg_5", "pc_ratio", "market_iv", "rv_iv_spread", "beta_60d",
)
_TRADE_CONTEXT = ("dir_short", "dte_frac", "moneyness", "bars_since_signal")


def _specs() -> dict[str, FeatureSpec]:
    specs: dict[str, FeatureSpec] = {}
    for name in _TECHNICAL:
        specs[name] = FeatureSpec(
            name, Availability.SIGNAL_CLOSE, "underlying 15m bar",
            "computed from the signal bar and earlier underlying bars",
        )
    for name in _SURFACE:
        specs[name] = FeatureSpec(
            name, Availability.PREVIOUS_SESSION_CLOSE, "daily option surface",
            "joined strictly as-of the prior completed session",
        )
    for name in _TRADE_CONTEXT:
        specs[name] = FeatureSpec(
            name, Availability.SIGNAL_CLOSE, "proposal metadata",
            "known when the signal is generated and the contract is selected",
        )
    specs["moneyness"] = FeatureSpec(
        "moneyness", Availability.SIGNAL_CLOSE, "configured proposal target",
        "log1p(MONEYNESS), independent of executed listed strike",
    )
    specs["prem_spot"] = FeatureSpec(
        "prem_spot", Availability.NEXT_OPTION_OPEN, "executed option fill",
        "the legacy value uses the first option-bar open after the signal",
    )
    return specs


FEATURE_SPECS: Mapping[str, FeatureSpec] = _specs()


def feature_spec(name: str) -> FeatureSpec:
    """Return a declared spec, including dynamically named one-hot features."""
    if name in FEATURE_SPECS:
        return FEATURE_SPECS[name]
    if name.startswith("strat_"):
        return FeatureSpec(
            name, Availability.SIGNAL_CLOSE, "proposal strategy identifier",
            "the strategy that emitted the proposal is known at signal time",
        )
    if name.startswith("sec_"):
        return FeatureSpec(
            name, Availability.SIGNAL_CLOSE, "static sector mapping",
            "static metadata available before the signal",
        )
    if name.startswith("spx0_"):
        # spx0 pool (docs/specs/SPX0_SPEC.md): every spx0_ feature is computed
        # from proxy 1m bars or option PRINTS at or before the signal bar close.
        return FeatureSpec(
            name, Availability.SIGNAL_CLOSE, "spx0 proxy 1m bars / option prints",
            "rolling windows and last prints ending at the signal bar close",
        )
    raise FeatureAvailabilityError(f"feature '{name}' has no availability declaration")


def violations(feature_names: Iterable[str], *,
               decision_at: Availability = Availability.SIGNAL_CLOSE) -> list[FeatureSpec]:
    """Return features that are unavailable at the requested decision point."""
    return [spec for name in feature_names if (spec := feature_spec(name)).available_at > decision_at]


def assert_decision_safe(feature_names: Iterable[str], *,
                         decision_at: Availability = Availability.SIGNAL_CLOSE) -> None:
    """Fail closed when a feature schema contains post-decision information."""
    bad = violations(feature_names, decision_at=decision_at)
    if not bad:
        return
    detail = ", ".join(f"{spec.name} ({spec.available_at.name})" for spec in bad)
    raise FeatureAvailabilityError(
        f"feature schema is not available by {decision_at.name}: {detail}"
    )


def v4_feature_names(legacy_feature_names: Iterable[str]) -> list[str]:
    """Return the v4 signal-close schema, preserving legacy feature ordering."""
    names = list(legacy_feature_names)
    safe = [name for name in names if feature_spec(name).available_at <= Availability.SIGNAL_CLOSE]
    assert_decision_safe(safe)
    return safe


def manifest(feature_names: Iterable[str]) -> list[dict[str, str]]:
    """Return a JSON-ready provenance manifest in model-feature order."""
    return [
        {
            "name": spec.name,
            "available_at": spec.available_at.name,
            "source": spec.source,
            "rationale": spec.rationale,
        }
        for name in feature_names
        for spec in [feature_spec(name)]
    ]
