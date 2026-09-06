"""Selection timing, invalid market data and deterministic D1 previews."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from nn_meta.live.contract_preview import ResolverPolicy, resolve_snapshot, format_preview

AT = "2026-09-08T14:30:30+00:00"
NS = int(datetime(2026, 9, 8, 14, 30, 25, tzinfo=timezone.utc).timestamp() * 1e9)


def contract(strike=650, delta=0.5, right="C", expiry="2026-09-18"):
    return {"details": {"ticker": f"O:SPY{expiry[2:].replace('-', '')}{right}{strike*1000:08d}",
                        "contract_type": "call" if right == "C" else "put",
                        "expiration_date": expiry, "strike_price": strike, "shares_per_contract": 100},
            "greeks": {"delta": delta}, "implied_volatility": 0.20, "open_interest": 1000,
            "last_quote": {"bid": 1.00, "ask": 1.02, "bid_size": 5, "ask_size": 4, "last_updated": NS}}


def snapshot(*rows):
    return {"observed_at": AT, "status": "OK", "results": list(rows or [contract()])}


def resolve(data, **kwargs):
    return resolve_snapshot(data, underlying="SPY", right=kwargs.pop("right", "C"),
                            target_dte=kwargs.pop("target_dte", 10), decision_at=AT,
                            policy=ResolverPolicy(max_spread_bps=500), **kwargs)


def test_expiry_then_delta_selection_and_order_invariance():
    rows = [contract(640, 0.7), contract(650, 0.51), contract(655, 0.50, expiry="2026-09-19")]
    result = resolve(snapshot(*rows))
    reversed_result = resolve(snapshot(*reversed(rows)))
    assert result["selected"]["strike"] == 650
    assert result["selected"] == reversed_result["selected"]
    assert result["preview_only"] is True
    assert "bid $1.00 / ask $1.02" in format_preview(result)


def test_put_delta_is_signed_and_wrong_right_is_excluded():
    result = resolve(snapshot(contract(), contract(645, -0.49, "P")), right="P")
    assert result["selected"]["occ"] == "SPY260918P00645000"
    assert result["rejections"] == {"wrong_right": 1}


@pytest.mark.parametrize("observed", ["2026-09-08T14:30:31Z", "2026-09-08T14:28:00Z", "2026-09-08T14:30:30"])
def test_snapshot_availability_cannot_be_inferred_from_old_quote(observed):
    data = snapshot(); data["observed_at"] = observed
    with pytest.raises(ValueError):
        resolve(data)


def test_incomplete_pagination_refuses_biased_selection():
    data = snapshot(); data["next_url"] = "https://api.massive.com/next"
    with pytest.raises(ValueError, match="pagination"):
        resolve(data)


@pytest.mark.parametrize("key,value,reason", [
    ("bid", 2.0, "invalid_quote"), ("bid", -1.0, "invalid_quote"),
    ("ask_size", 0, "invalid_quote"), ("ask", 2.0, "spread"),
    ("last_updated", NS - 90_000_000_000, "quote_unavailable_or_stale"),
    ("last_updated", NS + 10_000_000_000, "quote_unavailable_or_stale"),
])
def test_bad_quotes_never_become_preview_contracts(key, value, reason):
    row = contract(); row["last_quote"][key] = value
    result = resolve(snapshot(row))
    assert result["selected"] is None
    assert result["rejections"] == {reason: 1}


def test_snapshot_contents_bound_and_input_not_mutated():
    data = snapshot(); before = deepcopy(data)
    first = resolve(data)
    assert data == before
    data["results"][0]["open_interest"] += 1
    assert resolve(data)["snapshot_sha256"] != first["snapshot_sha256"]


def test_contract_identifier_must_match_details_and_deliverable():
    bad = contract(); bad["details"]["strike_price"] = 649
    adjusted = contract(655); adjusted["details"]["shares_per_contract"] = 150
    result = resolve(snapshot(bad, adjusted))
    assert result["selected"] is None
    assert result["rejections"] == {"malformed_contract": 1, "nonstandard_deliverable": 1}


def test_missing_greeks_no_moneyness_substitution():
    row = contract(); row.pop("greeks")
    result = resolve(snapshot(row))
    assert result["selected"] is None
    assert result["rejections"] == {"malformed_contract": 1}


def test_duplicate_contracts_refuse_order_dependent_selection():
    first = contract(); second = contract(delta=0.6)
    second["details"]["ticker"] = second["details"]["ticker"].removeprefix("O:")
    for rows in [(first, second), (second, first)]:
        with pytest.raises(ValueError, match="duplicate contract"):
            resolve(snapshot(*rows))


def test_quote_one_nanosecond_after_observation_is_unavailable():
    row = contract(); row["last_quote"]["last_updated"] = NS + 5_000_000_001
    result = resolve(snapshot(row))
    assert result["selected"] is None
    assert result["rejections"] == {"quote_unavailable_or_stale": 1}


def test_accepted_quote_retains_exact_nanoseconds():
    row = contract(); row["last_quote"]["last_updated"] = NS + 123456789
    result = resolve(snapshot(row))
    assert result["selected"]["quote_timestamp_ns"] == NS + 123456789
    assert result["selected"]["quoted_at"].endswith("25.123456789+00:00")


def test_snapshot_submicrosecond_precision_cannot_silently_truncate():
    data = snapshot(); data["observed_at"] = "2026-09-08T14:30:30.000000001Z"
    with pytest.raises(ValueError, match="microsecond precision"):
        resolve(data)


def test_snapshot_alone_does_not_verify_standard_deliverables():
    result = resolve(snapshot())
    assert result["selected"]["deliverables_verified"] is False
    assert "contract_reference_deliverables" in result["pending_requirements"]
    row = contract(); row["details"]["additional_underlyings"] = [{"type": "currency", "amount": 6.53}]
    result = resolve(snapshot(row))
    assert result["selected"] is None
    assert result["rejections"] == {"nonstandard_deliverable": 1}


def test_numeric_policy_values_are_normalized_before_use():
    policy = ResolverPolicy(max_spread_bps="500", target_delta="0.5")
    assert policy.max_spread_bps == 500.0
    result = resolve_snapshot(snapshot(), underlying="SPY", right="C", target_dte=10,
                              decision_at=AT, policy=policy)
    assert result["selected"] is not None


@pytest.mark.parametrize("kwargs", [{"max_spread_bps": -1}, {"max_spread_bps": float("inf")},
                                    {"max_spread_bps": 100, "target_delta": 2}])
def test_invalid_policies_fail(kwargs):
    with pytest.raises(ValueError):
        ResolverPolicy(**kwargs)
