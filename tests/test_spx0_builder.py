"""spx0 builder on a synthetic session: causal fills, signal/stop/floor exits,
marks bounded by the fills, unexecuted proposals kept. No archive access."""
import numpy as np
import pandas as pd

from nn_meta.mark_stream import stable_trade_id, validate_mark_stream
from nn_meta.spx0 import config as sc
from nn_meta.spx0.build_dataset import (SPX0_META_FEATURES, TECHNICALS,
                                        build_session_rows, proxy_context_features,
                                        resample_5m)
from nn_meta.spx0.contracts import parse_occ_frame
from nn_meta.spx0.fills import DepthPolicy

DAY = pd.Timestamp("2025-06-10")
OPEN = pd.Timestamp("2025-06-10 13:30")


def _proxy():
    idx = pd.date_range(OPEN, periods=390, freq="1min")
    close = 590 + np.linspace(0, 2, 390)
    return pd.DataFrame({"Open": close, "High": close + 0.1, "Low": close - 0.1,
                         "Close": close, "Volume": 1000.0}, index=idx)


def _options():
    rows = []
    ts = pd.date_range(OPEN, periods=390, freq="1min")
    for k in (5880, 5890, 5900, 5910, 5920, 5930):
        for right in "CP":
            occ = f"SPXW250610{right}{k*1000:08d}"
            prem = np.linspace(1.0, 0.5, 390) if right == "C" else np.linspace(0.8, 0.4, 390)
            for t, p in zip(ts, prem):
                rows.append({"occ": occ, "timestamp": t, "Open": p, "High": p + 0.02,
                             "Low": p - 0.02, "Close": p, "Volume": 20})
    df = pd.DataFrame(rows)
    df = pd.concat([df, parse_occ_frame(df["occ"])], axis=1)
    return df


def _prepared(bars5, entry_at, exit_at):
    idx = bars5.index
    z = pd.Series(False, index=idx)
    entries = z.copy(); entries.loc[entry_at] = True
    exits = z.copy(); exits.loc[exit_at] = True
    feats = pd.DataFrame(0.0, index=idx, columns=TECHNICALS)
    return {"rsi": ((entries, exits, z.copy(), z.copy()), feats)}


def _run(entry_at, exit_at, **kw):
    px = _proxy()
    b5 = resample_5m(px)
    rows, marks = build_session_rows(
        DAY, "SPX", proxy_1m=px, bars_5m=b5, options=_options(),
        prepared=_prepared(b5, entry_at, exit_at), ctx_1m=proxy_context_features(px), **kw)
    return pd.DataFrame(rows), pd.DataFrame(marks)


def test_signal_exit_is_causal_and_marks_are_bounded_by_fills():
    t_in, t_out = pd.Timestamp("2025-06-10 14:00"), pd.Timestamp("2025-06-10 15:00")
    ds, marks = _run(t_in, t_out)
    assert len(ds) == 1
    r = ds.iloc[0]
    assert r["executed"] and r["symbol"] == "SPX-C" and r["dte"] == 0
    assert r["fill_entry_ts"] > r["entry_ts"] and r["fill_lag_s"] == 60
    assert r["exit_reason"] == "signal" and r["fill_exit_ts"] >= t_out
    assert r["entry_premium"] > 0 and r["net_return"] < r["gross_return"]
    # every feature present; contract-declared names only
    assert set(SPX0_META_FEATURES) <= set(ds.columns)
    # marks: unique, entry+exit present, ids match the dataset's stable key
    vm = validate_mark_stream(marks)
    tid = stable_trade_id(ds).iloc[0]
    assert set(vm["trade_id"].astype(str)) == {tid}
    assert vm["mark_ts"].min() == r["fill_entry_ts"] and vm["mark_ts"].max() == r["fill_exit_ts"]
    assert np.isclose(vm.sort_values("mark_ts")["gross_return"].iloc[-1], r["gross_return"])


def test_stop_fires_before_the_signal_exit():
    # premium path drifts 1.0 -> 0.5 over the day; a 70% stop triggers well before 15:00
    t_in, t_out = pd.Timestamp("2025-06-10 14:00"), pd.Timestamp("2025-06-10 19:55")
    ds, _ = _run(t_in, t_out, exit_policy=sc.ExitPolicy(name="s70", stop_frac=0.70,
                                                         target_mult=5.0))
    r = ds.iloc[0]
    assert r["exit_reason"] == "stop_target" and r["fill_exit_ts"] < t_out


def test_no_depth_entry_is_kept_as_an_unexecuted_proposal():
    t_in, t_out = pd.Timestamp("2025-06-10 14:00"), pd.Timestamp("2025-06-10 15:00")
    ds, marks = _run(t_in, t_out, depth=DepthPolicy(qty=100, depth_mult=2.0))
    r = ds.iloc[0]
    assert not r["executed"] and r["exit_reason"] == "no_depth_entry"
    assert np.isnan(r["net_return"]) and marks.empty


def test_late_signals_near_the_close_are_not_proposed():
    t_in = pd.Timestamp("2025-06-10 19:45")           # inside the last 30 minutes
    ds, _ = _run(t_in, pd.Timestamp("2025-06-10 19:55"))
    assert ds.empty
