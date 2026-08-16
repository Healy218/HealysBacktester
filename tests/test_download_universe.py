"""Universe filter: the frozen research window vs the live-horizon refresh.

The 2026-08-16 production find: the deployed scanner's chain ends at
WINDOW_END + DTE_MAX because the universe filter clips every contract's
entry-eligible span to the frozen research window — so the live chain
silently empties when that horizon passes. ``--live-horizon`` rebuilds the
universe through today+N without touching the frozen window constants.
"""
import pandas as pd

from nn_meta import config
from nn_meta.download_universe import _universe_for


def _closes():
    return pd.Series(100.0, index=pd.bdate_range("2026-05-01", "2026-08-14"))


def test_frozen_window_drops_post_horizon_expiries():
    beyond = (pd.Timestamp(config.WINDOW_END)
              + pd.Timedelta(days=config.DTE_MAX + 30))
    contracts = pd.DataFrame({"expiration": [beyond], "strike": [100.0]})
    assert not _universe_for(contracts, _closes()).iloc[0]


def test_live_horizon_keeps_future_expiries_at_current_moneyness():
    beyond = (pd.Timestamp(config.WINDOW_END)
              + pd.Timedelta(days=config.DTE_MAX + 30))
    contracts = pd.DataFrame({"expiration": [beyond, beyond],
                              "strike": [100.0, 500.0]})
    keep = _universe_for(contracts, _closes(),
                         win_end=str((beyond + pd.Timedelta(days=30)).date()))
    assert keep.iloc[0]          # ATM strike vs the latest closes → kept
    assert not keep.iloc[1]      # far-OTM strike still filtered by the band


def test_default_behavior_unchanged_inside_the_window():
    inside = pd.Timestamp(config.WINDOW_END) - pd.Timedelta(days=10)
    contracts = pd.DataFrame({"expiration": [inside], "strike": [100.0]})
    closes = pd.Series(100.0, index=pd.bdate_range("2026-04-01", "2026-06-30"))
    assert _universe_for(contracts, closes).iloc[0]
