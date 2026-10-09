import math

from nn_meta import v9_alt as A


def test_parse_analyst_actions():
    assert A.parse_analyst("JP Morgan Maintains Neutral on Toast, Raises Price Target to $36") == ("pt_raise", "JP Morgan", 36.0)
    assert A.parse_analyst("Rosenblatt Maintains Neutral on AAOI, Lowers Price Target to $8")[0] == "pt_cut"
    assert A.parse_analyst("Goldman Sachs Upgrades Nvidia to Buy, Raises Price Target to $1,100")[::2] == ("upgrade", 1100.0)
    a = A.parse_analyst("Morgan Stanley Downgrades Intel to Underweight")
    assert a[0] == "downgrade" and math.isnan(a[2])
    assert A.parse_analyst("Nvidia shares rise after earnings") is None


def test_parse_earnings_with_negative_and_units():
    e = A.parse_earnings("Okta Q1 Adj. EPS $(0.10) Beats $(0.20) Estimate, Sales $251.00M Beat $238.31M Estimate")
    assert e == {"eps_act": -0.1, "eps_est": -0.2, "sales_act": 251e6, "sales_est": 238.31e6}
    assert abs(A.surprise(e["eps_act"], e["eps_est"]) - 0.5) < 1e-12
