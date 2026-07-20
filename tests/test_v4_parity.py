import pandas as pd
import pytest

from nn_meta.live.v4_parity import FeatureParityError, assert_feature_parity


def test_equal_causal_rows_pass():
    row = pd.DataFrame([{"rsi14": 0.5, "moneyness": None, "strat_rsi": 1.0}])
    assert_feature_parity(row, row.copy(), ["rsi14", "moneyness", "strat_rsi"])


def test_different_value_or_post_decision_feature_fails():
    with pytest.raises(FeatureParityError, match="mismatch"):
        assert_feature_parity(pd.DataFrame([{"rsi14": 0.5}]),
                              pd.DataFrame([{"rsi14": 0.6}]), ["rsi14"])
    with pytest.raises(ValueError, match="not available"):
        assert_feature_parity(pd.DataFrame([{"prem_spot": 1.0}]),
                              pd.DataFrame([{"prem_spot": 1.0}]), ["prem_spot"])
