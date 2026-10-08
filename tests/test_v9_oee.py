import numpy as np
import pandas as pd

from nn_meta import v8_vol, v9_oee

DAYS = ["2024-05-13", "2024-05-14", "2024-05-15", "2024-05-16", "2024-05-17",
        "2024-05-20", "2024-05-21", "2024-05-22", "2024-05-23", "2024-05-24"]


def test_event_days_by_release_session():
    tau = pd.Series(pd.to_datetime([
        "2024-05-21 20:05:00",   # 16:05 ET after close → enter 05-21, react 05-22
        "2024-05-21 11:00:00",   # 07:00 ET pre-market → enter 05-20, react 05-21
        "2024-05-21 16:00:00",   # 12:00 ET intraday → enter 05-20, react 05-21
        "2024-05-24 21:00:00",   # after the last close → off grid
    ], utc=True))
    e, r = v9_oee.event_days(tau, DAYS)
    assert [DAYS[i] for i in e[:3]] == ["2024-05-21", "2024-05-20", "2024-05-20"]
    assert [DAYS[i] for i in r[:3]] == ["2024-05-22", "2024-05-21", "2024-05-21"]
    assert e[3] == -1 and r[3] == -1


def _chain(day, expiry, S, sigma, strikes):
    T = v9_oee._years(day, expiry)
    rows = []
    for K in strikes:
        for cp in "CP":
            p = float(v8_vol.black76(S, K, T, sigma, cp == "C"))
            rows.append({"date": day, "expiry": expiry, "cp": cp, "strike": float(K),
                         "close": round(p, 4), "volume": 10})
    return rows


def test_atm_iv_recovers_flat_vol():
    ch = pd.DataFrame(_chain("2024-05-21", "2024-05-24", 100.0, 0.8, range(90, 111)))
    F, iv = v9_oee.atm_iv(ch, 100.0, v9_oee._years("2024-05-21", "2024-05-24"))
    assert abs(F - 100) < 0.01 and abs(iv - 0.8) < 0.01


def test_event_row_straddle_runup_and_crush_flag():
    strikes = range(80, 121)
    rows = []
    for i, d in enumerate(DAYS[:8]):
        sigma = 0.5 + 0.1 * (i - 1) if d <= "2024-05-21" else 0.4      # run-up, then crush on R
        S = 100.0 if d <= "2024-05-21" else 108.0
        rows += _chain(d, "2024-05-24", S, sigma, strikes)
    ch = pd.DataFrame(rows)
    px = pd.DataFrame({"close": [100.0] * 7 + [108.0] * 3,
                       "open": [100.0] * 7 + [107.0] * 3}, index=DAYS)
    px["adj_close"], px["adj_open"] = px["close"], px["open"]
    ev = {"e": DAYS.index("2024-05-21"), "r": DAYS.index("2024-05-22")}
    out = v9_oee.event_row(ev, ch, DAYS, px)
    assert out["status"] == "ok" and out["front_expiry"] == "2024-05-24"
    assert out["straddle_strike"] == 100.0
    assert abs(out["implied_move"] - out["straddle_entry"] / 100) < 1e-12
    assert out["straddle_exit_how"] == "traded"
    assert abs(out["realized_move"] - np.log(1.08)) < 1e-12
    assert abs(out["atm_iv_front_e+0"] - 1.0) < 0.02 and abs(out["atm_iv_front_e-5"] - 0.5) < 0.02
    assert abs(out["iv_runup"] - 1.0) < 0.05
    assert out["iv_crush_day_before"] is False
    assert abs(out["call50_delta"] - 0.5) < 0.1 and abs(out["put50_delta"] + 0.5) < 0.1


def test_crush_on_entry_day_is_flagged():
    strikes = range(80, 121)
    rows = []
    for d in DAYS[:8]:
        sigma = 1.0 if d < "2024-05-21" else 0.4                  # crush already on E
        rows += _chain(d, "2024-05-24", 100.0, sigma, strikes)
    px = pd.DataFrame({"close": 100.0, "open": 100.0, "adj_close": 100.0, "adj_open": 100.0},
                      index=DAYS)
    ev = {"e": DAYS.index("2024-05-21"), "r": DAYS.index("2024-05-22")}
    out = v9_oee.event_row(ev, pd.DataFrame(rows), DAYS, px)
    assert out["iv_crush_day_before"] is True
