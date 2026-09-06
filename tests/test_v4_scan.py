"""The [v4] live expert pass: detection → causal scoring → labeled alerts.

Everything runs on synthetic fixtures with a stub GBT-shaped bundle — no
LightGBM, no TensorFlow, no network — per the suite's self-containment rule.
"""
import numpy as np
import pandas as pd
import pytest

from nn_meta import config
from nn_meta.live import v4_scan
from nn_meta.live.v4_scan import (alert_key, best_per_signal, candidate_frame,
                                  fill_context, fresh_proposals, scan_pass)
from nn_meta.v4_loader import V4Bundle


# ── fixtures ──────────────────────────────────────────────────────────────────

def _bars(days=8, per_day=26, seed=0):
    rng = np.random.default_rng(seed)
    idx = []
    for d in pd.bdate_range("2026-01-05", periods=days):
        idx += [d + pd.Timedelta(minutes=30) + pd.Timedelta(minutes=15 * b)
                for b in range(per_day)]
    idx = pd.DatetimeIndex(idx)
    close = 100 + np.cumsum(rng.normal(0, 0.1, len(idx)))
    return pd.DataFrame({"Open": close, "High": close + 0.1, "Low": close - 0.1,
                         "Close": close, "Volume": 1_000}, index=idx)


def _surface(sym="SPY"):
    return pd.DataFrame({
        "underlying": [sym, sym],
        "date": pd.to_datetime(["2026-01-05", "2026-01-06"]),
        "rvol_5": [0.15, 0.16], "rvol_21": [0.18, 0.18],
        "atm_iv_near": [0.20, 0.21], "atm_iv_far": [0.22, 0.22],
        "term_slope": [0.02, 0.01], "iv_chg_5": [0.0, 0.01],
        "pc_ratio": [0.9, 0.95]})


def _spec(strategies=("rsi", "ma")):
    return {"symbols": {"SPY": {
        "best_strategy": strategies[0],
        "strategies": {s: {"params": {}, "param_label": f"{s}-frozen", "dte": 5}
                       for s in strategies}}}}


class _StubModel:
    """predict_proba shaped like a fitted classifier; score rises with dte."""

    def __init__(self, base=0.30, dte_gain=0.01):
        self.base, self.dte_gain = base, dte_gain

    def predict_proba(self, rows):
        p = self.base + self.dte_gain * rows["dte_frac"].to_numpy() * max(config.DTE_GRID)
        return np.column_stack([1 - p, p])


def _bundle(threshold=0.5, base=0.30, dte_gain=0.01, features=None):
    from nn_meta.build_meta_dataset import V4_META_FEATURES
    return V4Bundle(family="gbt", mode="filter", threshold=threshold,
                    features=features or list(V4_META_FEATURES), eligible=True,
                    members=[{"model": _StubModel(base, dte_gain)}], config={})


class _Notifier:
    def __init__(self, ok=True):
        self.ok, self.sent = ok, []

    def send(self, message, title="Signal"):
        if self.ok:
            self.sent.append((title, message))
        return self.ok


def _fire_on_last_bar(monkeypatch, bars, strategies=("rsi",), direction=0):
    """Make propose_trades emit an entry landing exactly on the last bar for
    the given strategies (and an earlier entry so the gap path is exercised)."""
    last, prev = bars.index[-1], bars.index[-30]

    def fake_propose(b, strategy, params, start, end):
        if strategy in strategies:
            return [(prev, prev + pd.Timedelta(hours=2), direction),
                    (last, None, direction)]
        return []

    monkeypatch.setattr(v4_scan, "propose_trades", fake_propose)


# ── detection ────────────────────────────────────────────────────────────────

def test_fresh_proposals_fire_per_strategy_with_gap(monkeypatch):
    bars = _bars()
    _fire_on_last_bar(monkeypatch, bars, strategies=("rsi", "ma"))
    got = fresh_proposals("SPY", bars, _spec()["symbols"]["SPY"], ["rsi", "ma"])
    assert {f["strategy"] for f in got} == {"rsi", "ma"}
    assert all(f["entry_ts"] == bars.index[-1] for f in got)
    assert all(f["bars_since_signal"] == 29 for f in got)   # index[-30] → gap 29


def test_no_proposal_when_entry_is_stale(monkeypatch):
    bars = _bars()
    stale = bars.index[-5]

    def fake_propose(b, strategy, params, start, end):
        return [(stale, None, 0)]

    monkeypatch.setattr(v4_scan, "propose_trades", fake_propose)
    assert fresh_proposals("SPY", bars, _spec()["symbols"]["SPY"], ["rsi"]) == []


def test_candidate_frame_expands_dte_grid_at_atm():
    fresh = [{"symbol": "SPY", "strategy": "rsi", "direction": 1,
              "entry_ts": pd.Timestamp("2026-01-08 15:00"),
              "bars_since_signal": 4, "param_label": "", "spot": 101.5}]
    frame = candidate_frame(fresh)
    assert len(frame) == len(config.DTE_GRID)
    assert (frame["strike"] == 101.5).all()          # ATM target = spot
    assert set(frame["dte"]) == set(config.DTE_GRID)


# ── scoring & selection ──────────────────────────────────────────────────────

def test_best_per_signal_picks_model_preferred_dte():
    batch = candidate_frame(
        [{"symbol": "SPY", "strategy": "rsi", "direction": 0,
          "entry_ts": pd.Timestamp("2026-01-08 15:00"), "bars_since_signal": 1,
          "param_label": "", "spot": 100.0}])
    scores = batch["dte"].to_numpy() / 100.0          # rises with dte
    win = best_per_signal(batch, scores)
    assert len(win) == 1
    assert int(win["dte"].iloc[0]) == max(config.DTE_GRID)


def test_fill_context_populates_market_iv_and_spread_without_daily_cache(monkeypatch):
    bars = _bars()
    from nn_meta.live.v4_candidates import build_candidate_batch

    def no_daily_cache():
        raise FileNotFoundError("underlying_daily.parquet not on this host")

    monkeypatch.setattr(v4_scan, "rolling_beta_60d", no_daily_cache)
    props = candidate_frame(
        [{"symbol": "SPY", "strategy": "rsi", "direction": 0,
          "entry_ts": bars.index[-1], "bars_since_signal": 1,
          "param_label": "", "spot": 100.0}])
    batch = build_candidate_batch(props, {"SPY": bars}, _surface(), _spec())
    out = fill_context(batch, _surface())
    # SPY surface exists → market_iv joined as-of prior close; spread from row cols
    assert np.isfinite(out["market_iv"]).all()
    assert out["rv_iv_spread"].iloc[0] == pytest.approx(0.18 - 0.21)
    # beta cache absent in tests → degrades to NaN, never raises
    assert out["beta_60d"].isna().all()


# ── the full pass ────────────────────────────────────────────────────────────

def _run_pass(monkeypatch, tmp_path, *, bundle=None, notifier=None,
              strategies=("rsi",), now=None):
    bars = _bars()
    _fire_on_last_bar(monkeypatch, bars, strategies=strategies)
    notifier = notifier or _Notifier()
    summary = scan_pass(
        bundle=bundle or _bundle(threshold=0.5, base=0.9, dte_gain=0.0),
        spec=_spec(), surface=_surface(), bar_loader=lambda s: bars,
        notifier=notifier, now=now or (bars.index[-1] + pd.Timedelta(minutes=15))
        .to_pydatetime(), state_dir=tmp_path, paper=True)
    return summary, notifier, bars


def test_pass_alerts_with_v4_label_and_paper_tag(monkeypatch, tmp_path):
    summary, notifier, _ = _run_pass(monkeypatch, tmp_path)
    assert summary["alerted"] == 1 and summary["delivered"] == 1
    title, msg = notifier.sent[0]
    assert title.startswith("[v4] SPY")
    assert "paper" in msg and "P(win)" in msg and "prem_spot" not in msg


def test_pass_is_idempotent_per_bar(monkeypatch, tmp_path):
    s1, n1, bars = _run_pass(monkeypatch, tmp_path)
    assert s1["alerted"] == 1
    # same bar again → dedupe: nothing new alerted or delivered
    _fire_on_last_bar(monkeypatch, bars, strategies=("rsi",))
    n2 = _Notifier()
    s2 = scan_pass(bundle=_bundle(0.5, 0.9, 0.0), spec=_spec(),
                   surface=_surface(), bar_loader=lambda s: bars, notifier=n2,
                   now=(bars.index[-1] + pd.Timedelta(minutes=15)).to_pydatetime(),
                   state_dir=tmp_path, paper=True)
    assert s2["alerted"] == 0 and n2.sent == []


def test_below_threshold_signal_is_filtered_and_not_rescored(monkeypatch, tmp_path):
    summary, notifier, _ = _run_pass(
        monkeypatch, tmp_path, bundle=_bundle(threshold=0.9, base=0.2, dte_gain=0.0))
    assert summary["alerted"] == 0 and notifier.sent == []
    # filtered signals still land in the paper ledger? No — only kept ones do.
    ledger = (tmp_path / ".v4_paper_ledger.json")
    assert not ledger.exists() or ledger.read_text() in ("[]", "")


def test_failed_send_is_replayed_from_outbox(monkeypatch, tmp_path):
    bad = _Notifier(ok=False)
    s1, _, bars = _run_pass(monkeypatch, tmp_path, notifier=bad)
    assert s1["alerted"] == 1 and s1["delivered"] == 0      # queued, not lost
    # next pass with a working notifier delivers the queued alert
    good = _Notifier()
    s2 = scan_pass(bundle=_bundle(0.5, 0.9, 0.0), spec=_spec(),
                   surface=_surface(), bar_loader=lambda s: bars,
                   notifier=good,
                   now=(bars.index[-1] + pd.Timedelta(minutes=15)).to_pydatetime(),
                   state_dir=tmp_path, paper=True)
    assert s2["delivered"] == 1
    assert good.sent[0][0].startswith("[v4] SPY")


def test_kept_signal_opens_paper_position(monkeypatch, tmp_path):
    summary, _, _ = _run_pass(monkeypatch, tmp_path)
    assert summary["open_paper_positions"] == 1
    import json
    trades = json.loads((tmp_path / ".v4_paper_ledger.json").read_text())
    assert trades[0]["symbol"] == "SPY" and trades[0]["exit_price"] is None


def test_scan_error_is_counted_not_fatal(monkeypatch, tmp_path):
    def boom(sym):
        raise RuntimeError("provider down")
    summary = scan_pass(bundle=_bundle(0.5, 0.9, 0.0), spec=_spec(),
                        surface=_surface(), bar_loader=boom,
                        notifier=_Notifier(), state_dir=tmp_path, paper=True)
    assert summary["error_count"] == 1 and summary["alerted"] == 0


# ── ticker aliases (SQ → XYZ rename, audited 2026-08-16) ─────────────────────

def test_aliased_loader_fetches_renamed_ticker():
    from nn_meta.live.v4_scan import aliased_bar_loader
    requested = []

    def loader(sym):
        requested.append(sym)
        return _bars()

    wrapped = aliased_bar_loader(loader)
    wrapped("SQ")
    wrapped("SPY")
    assert requested == ["XYZ", "SPY"]      # renamed fetches new; others pass through


def test_alert_shows_tradable_ticker_for_renamed_symbol():
    from nn_meta.live.v4_scan import format_v4_alert
    row = pd.DataFrame([{"symbol": "SQ", "strategy": "rsi", "dte": 10,
                         "entry_ts": pd.Timestamp("2026-01-08 15:00"),
                         "score": 0.61}]).iloc[0]
    fresh = {"direction": 0, "param_label": "rsi-frozen", "spot": 55.0}
    title, msg = format_v4_alert(row, fresh, _bundle(), paper=True)
    assert "XYZ (fka SQ)" in title and "XYZ (fka SQ)" in msg


def test_atomic_bar_cache_write(tmp_path):
    from data.vbt_data_loader import _cache_df
    df = pd.DataFrame({"Close": [1.0, 2.0]},
                      index=pd.date_range("2026-01-05", periods=2))
    target = tmp_path / "SPY_15m_a_b.csv"
    _cache_df(df, str(target))
    assert target.exists()
    assert not list(tmp_path.glob("*.tmp.*"))       # no temp litter
    back = pd.read_csv(target, index_col=0, parse_dates=True)
    assert len(back) == 2


def test_expert_identity_follows_the_pool(monkeypatch):
    """Under NN_META_POOL=v5 the same module is the [v5] expert: its own
    labels, state files and default bundle dir; under anything else it stays
    [v4] (2026-09-05 v5 deploy)."""
    import importlib
    from nn_meta import config as cfg
    assert v4_scan.EXPERT == ("v5" if cfg.POOL == "v5" else "v4")
    assert v4_scan.WATCHLIST.name == f".{v4_scan.EXPERT}_watchlist.json"
    assert v4_scan.ALERT_STATE.name == f".{v4_scan.EXPERT}_alert_state.json"
    assert v4_scan.DEFAULT_BUNDLE_DIR.name == f"model_final_{'v5' if v4_scan.EXPERT == 'v5' else 'v4'}"
    assert ("v5", ".v5_watchlist.json") in v4_scan.PANEL_WATCHLISTS
    # flip the pool and re-import: everything renames together
    monkeypatch.setattr(cfg, "POOL", "v5")
    mod = importlib.reload(v4_scan)
    try:
        assert mod.EXPERT == "v5" and mod.TAG == "[v5]"
        assert mod.WATCHLIST.name == ".v5_watchlist.json"
        assert mod.DEFAULT_BUNDLE_DIR.name == "model_final_v5"
    finally:
        monkeypatch.undo()
        importlib.reload(v4_scan)
    assert v4_scan.EXPERT == ("v5" if cfg.POOL == "v5" else "v4")
