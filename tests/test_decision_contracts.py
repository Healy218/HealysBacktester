from datetime import date

import pandas as pd
import pytest

from nn_meta.decision_contracts import DecisionContractSelector
from options.data.provider import OptionContract


def contract(strike, *, delta=None):
    return OptionContract(f"SPY250117C{int(strike * 1000):08d}", "SPY",
                          date(2025, 1, 17), strike, "C", delta=delta)


class Provider:
    point_in_time_chain = True
    def __init__(self, chain):
        self.chain, self.calls = chain, []

    def get_chain(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return self.chain

    def get_contract_bars(self, *args, **kwargs):
        pytest.fail("selection must not inspect future option fills")


def test_selection_uses_prior_date_and_recomputes_spot_band_without_future_greeks():
    provider = Provider([contract(100, delta=.5), contract(125, delta=.01)])
    selector = DecisionContractSelector(provider)
    first = selector.request("SPY", signal_bar_open="2025-01-02T14:30:00Z",
                             raw_spot=100, right="C", target_dte=15)
    second = selector.request("SPY", signal_bar_open="2025-01-02T18:30:00Z",
                              raw_spot=125, right="C", target_dte=15)
    assert first["contract"].endswith("00100000")
    assert second["contract"].endswith("00125000")
    assert len(provider.calls) == 1
    assert provider.calls[0][1]["as_of"] == date(2025, 1, 1)
    assert "strike_gte" not in provider.calls[0][1]
    assert first["chain_available_ns"] <= first["raw_spot_available_ns"] == first["decision_close_ns"]
    assert first["window_end_ns"] - first["window_start_ns"] == 900_000_000_000


def test_tied_strikes_deterministic_and_no_contract_is_explicit():
    for chain in ([contract(101), contract(99)], [contract(99), contract(101)]):
        selector = DecisionContractSelector(Provider(chain))
        value = selector.request("SPY", signal_bar_open="2025-01-02T14:30:00Z",
                                 raw_spot=100, right="C", target_dte=15)
        assert value["contract"].endswith("00099000")
    value = DecisionContractSelector(Provider([])).request(
        "SPY", signal_bar_open="2025-01-02T14:30:00Z", raw_spot=100,
        right="C", target_dte=15)
    assert value["contract"] is None and value["status"] == "unselected"
    assert value["reason"]


@pytest.mark.parametrize("kwargs", [{"raw_spot":float("nan")}, {"raw_spot":True},
                                   {"target_dte":True}, {"right":"call"},
                                   {"signal_bar_open":"2025-01-02 14:30"}])
def test_invalid_decision_inputs_fail(kwargs):
    values = dict(signal_bar_open="2025-01-02T14:30:00Z", raw_spot=100,
                  right="C", target_dte=15)
    values.update(kwargs)
    with pytest.raises(ValueError):
        DecisionContractSelector(Provider([])).request("SPY", **values)


def test_expanded_execution_uses_exact_same_contract_policy_as_features():
    from options.execution import Execution
    from nn_meta.decision_contracts import POLICY_VERSION
    provider = Provider([contract(99, delta=.01), contract(101, delta=.5)])
    ex = Execution("SPY", "15m", "2025-01-31", provider,
                   {"DECISION_CHAIN_POLICY":POLICY_VERSION})
    expected = DecisionContractSelector(provider).request(
        "SPY", signal_bar_open="2025-01-02T14:30:00Z", raw_spot=100,
        right="C", target_dte=15)
    assert ex.select(date(2025, 1, 2), "C", 100, 15, spot_basis="raw").symbol == expected["contract"]
    with pytest.raises(ValueError, match="explicit raw"):
        ex.select(date(2025, 1, 2), "C", 100, 15)


def test_unverified_chain_provider_and_unbound_occ_root_fail():
    provider = Provider([])
    provider.point_in_time_chain = False
    with pytest.raises(ValueError, match="point-in-time"):
        DecisionContractSelector(provider)
    wrong = OptionContract("IWM250117C00100000", "SPY", date(2025, 1, 17), 100, "C")
    with pytest.raises(ValueError, match="root mismatch"):
        DecisionContractSelector(Provider([wrong])).select(
            "SPY", as_of=date(2025, 1, 2), right="C", raw_spot=100, target_dte=15)


def test_off_grid_decision_is_rejected():
    with pytest.raises(ValueError, match="grid"):
        DecisionContractSelector(Provider([])).request("SPY", signal_bar_open="2025-01-02T14:31:00Z",
                                                       raw_spot=100, right="C", target_dte=15)
