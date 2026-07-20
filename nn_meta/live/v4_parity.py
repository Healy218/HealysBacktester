"""Feature parity checks shared by offline V4 research and live candidates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from nn_meta.feature_contract import assert_decision_safe


class FeatureParityError(ValueError):
    pass


def assert_feature_parity(offline: pd.DataFrame, live: pd.DataFrame,
                          feature_names: list[str], *, atol: float = 1e-10) -> None:
    """Require exactly one comparable row and same ordered causal features."""
    assert_decision_safe(feature_names)
    if len(offline) != 1 or len(live) != 1:
        raise FeatureParityError("parity comparison requires exactly one offline and live row")
    missing = set(feature_names) - set(offline.columns) | (set(feature_names) - set(live.columns))
    if missing:
        raise FeatureParityError(f"missing parity features: {sorted(missing)}")
    for name in feature_names:
        left, right = offline.iloc[0][name], live.iloc[0][name]
        if pd.isna(left) and pd.isna(right):
            continue
        if pd.isna(left) != pd.isna(right) or not np.isclose(float(left), float(right), atol=atol, rtol=0):
            raise FeatureParityError(f"feature mismatch for {name}: offline={left!r}, live={right!r}")
