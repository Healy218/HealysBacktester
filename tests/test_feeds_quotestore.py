import json
import pandas as pd
from nn_meta.live.feeds.quotestore import QuoteStore, spread_bps
from nn_meta.live.feeds.option_stream import read_watch, add_to_watch


def test_quotestore_roundtrip_and_staleness(tmp_path):
    p = tmp_path / "q.json"
    s = QuoteStore(p)
    s.update("O:SPY260918C00650000", bid=1.20, ask=1.30, bid_size=10, ask_size=5,
             ts=pd.Timestamp("2026-09-01 14:30:00", tz="UTC"))
    assert s.flush() == 1
    q = QuoteStore.get("SPY260918C00650000", p)
    assert q["bid"] == 1.2 and q["ask"] == 1.3 and round(spread_bps(q)) == 800
    assert QuoteStore.get("SPY260918C00650000", p, max_age_s=1) is None      # stale
    assert QuoteStore.get("NOPE", p) is None


def test_watch_file_dedupes_normalizes_and_caps(tmp_path):
    w = tmp_path / "watch.json"
    assert add_to_watch(["O:SPY260918C00650000", "spy260918c00650000", "AAPL260918P00200000"], w) == 2
    assert read_watch(w) == ["AAPL260918P00200000", "SPY260918C00650000"]
    assert read_watch(tmp_path / "missing.json") == []
