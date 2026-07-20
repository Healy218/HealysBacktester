"""Regression tests for the v4 signal-time feature contract."""
import pytest

from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.feature_contract import (
    Availability,
    FeatureAvailabilityError,
    assert_decision_safe,
    feature_spec,
    manifest,
    v4_feature_names,
    violations,
)


def test_every_legacy_feature_has_an_availability_declaration():
    assert [feature_spec(name).name for name in META_FEATURES] == META_FEATURES


def test_premium_at_next_option_open_is_rejected_at_signal_close():
    bad = violations(META_FEATURES)
    assert [spec.name for spec in bad] == ["prem_spot"]
    assert bad[0].available_at is Availability.NEXT_OPTION_OPEN
    with pytest.raises(FeatureAvailabilityError, match="prem_spot"):
        assert_decision_safe(META_FEATURES)


def test_v4_schema_keeps_order_and_excludes_post_decision_premium():
    features = v4_feature_names(META_FEATURES)
    assert "prem_spot" not in features
    assert features == [name for name in META_FEATURES if name != "prem_spot"]
    assert V4_META_FEATURES == features
    assert_decision_safe(features)


def test_unknown_feature_fails_closed():
    with pytest.raises(FeatureAvailabilityError, match="no availability declaration"):
        assert_decision_safe(["unknown_future_feature"])


def test_manifest_records_feature_provenance_in_schema_order():
    rows = manifest(["rsi14", "prem_spot", "strat_rsi"])
    assert [row["name"] for row in rows] == ["rsi14", "prem_spot", "strat_rsi"]
    assert rows[1]["available_at"] == "NEXT_OPTION_OPEN"
