# tests/test_universe_pit.py — stage B of the PIT universe (spec gates).
import json

import pandas as pd
import pytest

from nn_meta import universe_pit as up


# ── synthetic daily rows ─────────────────────────────────────────────────────

def _days(start, n):
    return pd.bdate_range(start, periods=n)


def make_daily(tickers_vol: dict[str, float], days) -> pd.DataFrame:
    """One row per (root, day), constant dollar volume per root."""
    rows = [{"root": t, "date": d.date().isoformat(), "opt_dollar_vol": v,
             "call_dollar_vol": v / 2, "put_dollar_vol": v / 2,
             "n_contracts": 10, "n_trades": 100}
            for t, v in tickers_vol.items() for d in days]
    return pd.DataFrame(rows)


# 130 business days from 2024-08-01 spans Aug→Jan; first full 63-day window
# lands in month 3 (Oct).
DAYS = _days("2024-08-01", 130)


def small_universe(n=8, base=1e9):
    # TAA most liquid … THH least
    return {f"T{c}{c}": base / (i + 1) for i, c in enumerate("ABCDEFGH"[:n])}


def small_membership(**kw):
    daily = make_daily(small_universe(), DAYS)
    return up.monthly_membership(daily, enter_rank=4, exit_rank=6,
                                 window_days=63, min_active_days=50, **kw)


# ── OCC parsing / mapping ────────────────────────────────────────────────────

def test_split_occ():
    assert up.split_occ("O:AAPL241220C00150000") == ("AAPL", "C")
    assert up.split_occ("O:AAPL1241220P00150000") == ("AAPL1", "P")
    assert up.split_occ("O:SPXW240816C05400000") == ("SPXW", "C")
    assert up.split_occ("AAPL") is None            # not an option
    assert up.split_occ("O:241220C00150000") is None  # no root


def test_root_to_ticker_drops_index_and_adjusted_maps_aliases():
    assert up.root_to_ticker("AAPL") == "AAPL"
    assert up.root_to_ticker("SQ") == "XYZ"        # TICKER_ALIASES rename
    assert up.root_to_ticker("AAPL1") is None      # adjusted series
    assert up.root_to_ticker("SPXW") is None       # index root
    assert up.root_to_ticker("VIX") is None


# ── stage A transform ────────────────────────────────────────────────────────

def test_daily_rows_from_day_aggs():
    df = pd.DataFrame([
        {"ticker": "O:AAPL241220C00150000", "close": 2.0, "volume": 10, "transactions": 5},
        {"ticker": "O:AAPL241220P00150000", "close": 1.0, "volume": 4, "transactions": 2},
        {"ticker": "O:TSLA241220C00250000", "close": 5.0, "volume": 1, "transactions": 1},
        {"ticker": "GARBAGE", "close": 9.9, "volume": 99, "transactions": 9},
    ])
    rows = up.daily_rows_from_day_aggs(df, "2024-12-01")
    assert list(rows.columns) == up.DAILY_COLUMNS
    aapl = rows[rows["root"] == "AAPL"].iloc[0]
    assert aapl["opt_dollar_vol"] == 2.0 * 10 * 100 + 1.0 * 4 * 100
    assert aapl["call_dollar_vol"] == 2000.0 and aapl["put_dollar_vol"] == 400.0
    assert aapl["n_contracts"] == 2 and aapl["n_trades"] == 7
    assert set(rows["root"]) == {"AAPL", "TSLA"}
    assert (rows["date"] == "2024-12-01").all()


def test_daily_rows_empty_parse_is_loud():
    df = pd.DataFrame([{"ticker": "GARBAGE", "close": 1.0, "volume": 1,
                        "transactions": 1}])
    with pytest.raises(up.UniversePitError, match="no OCC rows"):
        up.daily_rows_from_day_aggs(df, "2024-12-01")
    with pytest.raises(up.UniversePitError, match="missing columns"):
        up.daily_rows_from_day_aggs(df.drop(columns=["volume"]), "2024-12-01")


# ── stage B: reconstitution mechanics ────────────────────────────────────────

def test_membership_ranks_and_short_window_months_skipped():
    m = small_membership()
    months = sorted(m["month"].unique())
    assert months[0] == "2024-10"       # Aug/Sep lack a full 63-day window
    top = m[m["month"] == "2024-10"].sort_values("rank")
    assert list(top["ticker"]) == ["TAA", "TBB", "TCC", "TDD"]  # enter_rank=4
    assert top["entered"].all()         # first reconstitution: all new


def test_no_lookahead_spike_next_month_does_not_move_this_month():
    daily = make_daily(small_universe(), DAYS)
    m_before = up.monthly_membership(daily, enter_rank=4, exit_rank=6,
                                     window_days=63, min_active_days=50)
    # THH (illiquid) explodes in November; October membership must not move
    spike = daily["date"] >= "2024-11-01"
    daily.loc[spike & (daily["root"] == "THH"), "opt_dollar_vol"] = 1e12
    m_after = up.monthly_membership(daily, enter_rank=4, exit_rank=6,
                                    window_days=63, min_active_days=50)
    oct_b = m_before[m_before["month"] == "2024-10"].reset_index(drop=True)
    oct_a = m_after[m_after["month"] == "2024-10"].reset_index(drop=True)
    pd.testing.assert_frame_equal(oct_b, oct_a)
    assert "THH" in set(m_after[m_after["month"] == "2024-12"]["ticker"])


def test_hysteresis_band_keeps_member_until_exit_rank():
    vols = small_universe()
    daily = make_daily(vols, DAYS)
    # TDD enters at rank 4 in Oct, then decays to rank 5 (inside the 4..6
    # band → stays), never past 6 → never exits.
    late = daily["date"] >= "2024-10-01"
    daily.loc[late & (daily["root"] == "TDD"), "opt_dollar_vol"] = vols["TEE"] * 0.99
    m = up.monthly_membership(daily, enter_rank=4, exit_rank=6,
                              window_days=63, min_active_days=50)
    last = sorted(m["month"].unique())[-1]
    grp = m[m["month"] == last].set_index("ticker")
    assert "TDD" in grp.index and grp.loc["TDD", "rank"] > 4
    # TEE, now rank 4, entered
    assert "TEE" in grp.index


def test_delisting_exits_membership_and_marks_prior_month():
    vols = small_universe()
    daily = make_daily(vols, DAYS)
    # TBB stops trading Nov 1 (delisted): drop all later rows
    daily = daily[~((daily["root"] == "TBB") & (daily["date"] >= "2024-11-01"))]
    m = up.monthly_membership(daily, enter_rank=4, exit_rank=6,
                              window_days=63, min_active_days=50)
    months_with_t01 = sorted(m[m["ticker"] == "TBB"]["month"])
    assert months_with_t01                      # was a member while alive
    assert months_with_t01[-1] <= "2024-12"     # gone once active days decay
    last_row = m[(m["ticker"] == "TBB") & (m["month"] == months_with_t01[-1])]
    assert last_row["exited"].item() is True    # stint end marked
    up.assert_canaries(m, {"TBB": "2025-01"})   # canary helper agrees


def test_available_at_is_first_trading_day_after_month_end():
    m = small_membership()
    oct_rows = m[m["month"] == "2024-10"]
    # 2024-10-31 is a Thursday; next business day is Nov 1
    assert (oct_rows["available_at"] == "2024-11-01").all()


def test_through_caps_partial_final_month():
    m = small_membership(through="2024-11")
    assert sorted(m["month"].unique()) == ["2024-10", "2024-11"]


# ── gates ────────────────────────────────────────────────────────────────────

def test_delisting_canary_gate_refuses_churn_free_history():
    frames = []
    for i, month in enumerate(pd.period_range("2024-01", periods=13, freq="M")):
        frames.append(pd.DataFrame({
            "month": str(month), "ticker": ["A", "B"], "rank": [1, 2],
            "score": [2.0, 1.0], "entered": i == 0, "exited": False,
            "available_at": f"{month}-28"}))
    frozen = pd.concat(frames, ignore_index=True)
    with pytest.raises(up.UniversePitError, match="delisting canary"):
        up.delisting_canary_gate(frozen)
    up.delisting_canary_gate(frozen, min_months=20)     # too short to judge
    churned = frozen[~((frozen["ticker"] == "B") & (frozen["month"] >= "2024-06"))]
    up.delisting_canary_gate(churned)                   # churn present: passes


def test_assert_canaries_rejects_ghost_membership():
    m = small_membership()
    with pytest.raises(up.UniversePitError, match="still a member"):
        up.assert_canaries(m, {"TAA": "2024-11"})       # alive past "death"
    with pytest.raises(up.UniversePitError, match="never a member"):
        up.assert_canaries(m, {"ZZZ": "2024-12"})


def test_churn_report():
    m = small_membership()
    rep = up.churn_report(m)
    assert rep[0]["month"] == "2024-10" and rep[0]["n_members"] == 4
    assert rep[0]["entries"] == ["TAA", "TBB", "TCC", "TDD"]
    assert all(not r["exits"] for r in rep)     # constant vols: no churn


# ── freeze / load round-trip ─────────────────────────────────────────────────

def test_freeze_month_write_once_and_load(tmp_path):
    m = small_membership()
    p = up.freeze_month(m, "2024-10", artifact_dir=tmp_path)
    payload = json.loads(p.read_text())
    assert payload["month"] == "2024-10"
    assert payload["members"][0]["rank"] == 1
    assert payload["churn"]["entries"] == ["TAA", "TBB", "TCC", "TDD"]
    with pytest.raises(up.UniversePitError, match="already frozen"):
        up.freeze_month(m, "2024-10", artifact_dir=tmp_path)
    with pytest.raises(up.UniversePitError, match="no membership rows"):
        up.freeze_month(m, "2030-01", artifact_dir=tmp_path)

    up.freeze_month(m, "2024-11", artifact_dir=tmp_path)
    loaded = up.load_membership(tmp_path)
    assert set(loaded["month"]) == {"2024-10", "2024-11"}
    assert {"ticker", "rank", "score", "entered", "available_at"} <= set(loaded.columns)


def test_members_asof_uses_previous_reconstitution_only(tmp_path):
    m = small_membership()
    for month in sorted(m["month"].unique()):
        up.freeze_month(m, month, artifact_dir=tmp_path)
    loaded = up.load_membership(tmp_path)
    # during November, only October's freeze (available 2024-11-01) is usable
    assert up.members_asof(loaded, "2024-11") == {"TAA", "TBB", "TCC", "TDD"}
    # before any freeze is available: empty, never a guess
    assert up.members_asof(loaded, "2024-09") == set()


def test_load_daily_rows_absent_is_loud(tmp_path):
    with pytest.raises(up.UniversePitError, match="no universe_daily"):
        up.load_daily_rows(tmp_path)
