from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from nn_meta.execution_validation import (QuoteTape, QuotePolicy, replay_quotes,
    checked_ledger, aggregate_latency)
from nn_meta.v4_accounting import AccountingDataError, CostScenario, classify_quote

CONTRACT = "SPY260918C00650000"


def tape(times, bids, asks=None):
    times = pd.to_datetime(times, utc=True)
    return pd.DataFrame(dict(contract=CONTRACT, quote_ts=times, available_at=times,
        bid=bids, ask=np.asarray(bids) + .02 if asks is None else asks, bid_size=10, ask_size=10))


def plans():
    p = pd.DataFrame([dict(trade_id="one", symbol="SPY", signal_ts="2026-09-14T14:45:00Z")])
    l = pd.DataFrame([dict(trade_id="one", leg_index=0, contract=CONTRACT,
        entry_decision_ts="2026-09-14T14:45:00Z", exit_decision_ts="2026-09-14T14:46:00Z",
        expiration_ts="2026-09-18T20:00:00Z")])
    return p, l


def test_quotes_pay_actual_spread_and_dollar_commission_with_independent_equity():
    frame = tape(["2026-09-14T14:45:01Z", "2026-09-14T14:45:30Z", "2026-09-14T14:46:00Z"], [1., .8, 1.5])
    policy = QuotePolicy()
    tr, marks, audit = replay_quotes(*plans(), QuoteTape(frame), policy=policy)
    result, curve = checked_ledger(tr, marks, max_concurrent=1, position_fraction=1,
                                   costs=CostScenario(name=policy.name, fee=0, slippage=0))
    assert result["total_return"] == pytest.approx((1.5 - .0065) / (1.02 + .0065) - 1)
    assert result["max_drawdown"] > .20
    assert result["cost_model"] == "option_quote" and result["independent_ledger_match"]
    assert result["turnover"] == pytest.approx((1.02 + 1.5) / (1.02 + .0065))
    assert audit.empty
    expensive = replace(policy, commission_per_contract=1.30, slippage_bps=25)
    tr2, m2, _ = replay_quotes(*plans(), QuoteTape(frame), policy=expensive)
    result2, _ = checked_ledger(tr2, m2, max_concurrent=1, position_fraction=1,
                                costs=CostScenario(name=policy.name, fee=0, slippage=0))
    assert result2["total_return"] < result["total_return"]


def test_latency_limit_and_future_quotes_cannot_fill():
    p, l = plans()
    l["exit_decision_ts"] = "2026-09-14T15:30:00Z"
    frame = tape(["2026-09-14T14:51:00Z"], [1.])
    tr, _, audit = replay_quotes(p, l, QuoteTape(frame))
    assert tr.empty and len(audit) == 1
    quote, _ = QuoteTape(frame).quote(CONTRACT, pd.Timestamp("2026-09-14T14:50:59.999999999Z"), QuotePolicy())
    assert quote is None


def test_new_invalid_quote_supersedes_old_valid_and_missing_exit_is_loss():
    frame = tape(["2026-09-14T14:45:01Z", "2026-09-14T14:45:59Z"], [1., 0.])
    tr, marks, audit = replay_quotes(*plans(), QuoteTape(frame))
    assert tr.gross_return.iloc[0] == -1
    assert "zero_bid" in set(audit.reason)
    result, _ = checked_ledger(tr, marks, max_concurrent=1, position_fraction=1,
                               costs=CostScenario(name="quotes_base", fee=0, slippage=0))
    assert result["total_return"] == -1


@pytest.mark.parametrize("bid,ask", [(np.inf, np.inf), (-1, 1), (1, np.inf), ("bad", 2)])
def test_nonfinite_or_invalid_quotes_never_fill(bid, ask):
    assert classify_quote(bid, ask) is not None


def test_negative_or_missing_quote_age_never_fills():
    assert classify_quote(1, 1.02, quote_age=pd.Timedelta(-1)) is not None
    assert classify_quote(1, 1.02, quote_age=pd.NaT) is not None


def test_rolls_charge_each_leg_and_failed_roll_retains_cash_and_drawdown():
    p, l = plans()
    second = dict(l.iloc[0], leg_index=1, entry_decision_ts="2026-09-14T14:46:00Z",
                  exit_decision_ts="2026-09-14T14:47:00Z")
    l = pd.concat([l, pd.DataFrame([second])], ignore_index=True)
    frame = tape(["2026-09-14T14:45:01Z", "2026-09-14T14:46:00Z", "2026-09-14T14:46:01Z", "2026-09-14T14:47:00Z"],
                 [1., 1.5, 2., 2.5])
    tr, marks, _ = replay_quotes(p, l, QuoteTape(frame))
    result, _ = checked_ledger(tr, marks, max_concurrent=1, position_fraction=1,
                               costs=CostScenario(name="quotes_base", fee=0, slippage=0))
    assert result["total_return"] == pytest.approx((1.5-.0065)/(1.02+.0065)*(2.5-.0065)/(2.02+.0065)-1)
    l.loc[1, "contract"] = "SPY260918C00655000"
    tr, marks, audit = replay_quotes(p, l, QuoteTape(frame))
    result, _ = checked_ledger(tr, marks, max_concurrent=1, position_fraction=1,
                               costs=CostScenario(name="quotes_base", fee=0, slippage=0))
    assert result["total_return"] == pytest.approx((1.5-.0065)/(1.02+.0065)-1)
    assert audit.iloc[0].conservative


def test_missing_leg_and_expired_plan_fail_closed():
    p, l = plans()
    with pytest.raises(AccountingDataError, match="exact complete"):
        replay_quotes(p, l.iloc[:0], QuoteTape(tape([], [])))
    l["expiration_ts"] = "2026-09-14T14:45:30Z"
    with pytest.raises(AccountingDataError, match="expired"):
        replay_quotes(p, l, QuoteTape(tape([], [])))


def test_aggregate_latency_uses_signal_close_not_bar_start():
    from tests.test_v4_accounting import _trades, _marks
    tr, marks, reject = aggregate_latency(_trades(), _marks(), max_delay_seconds=0)
    assert len(tr) == 2 and reject.empty
    late = _trades(); late.loc[0, "fill_entry_ts"] += pd.Timedelta(seconds=1)
    tr, marks, reject = aggregate_latency(late, _marks(), max_delay_seconds=0)
    assert len(tr) == 1 and reject.delay_seconds.iloc[0] == 1
