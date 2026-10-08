"""V8 option spread extraction: OCC parsing and NBBO snapshots."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "build_v8_option_spreads",
    Path(__file__).resolve().parent.parent / "scripts" / "build_v8_option_spreads.py")
osp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(osp)

M = 60 * 10**9


def test_parse_occ():
    assert osp.parse_occ("AAPL220318C00152500") == ("AAPL", "2022-03-18", "C", 152.5)
    assert osp.parse_occ("O:SPY241220P00450000") == ("SPY", "2024-12-20", "P", 450.0)
    assert osp.parse_occ("garbage") is None


def test_snapshots_use_last_quote_and_skip_invalid():
    def q(t, bid, ask):
        return {"sip_timestamp": t, "bid_price": bid, "ask_price": ask,
                "bid_size": 1, "ask_size": 1}
    recs = [q(1 * M, 1.0, 1.1), q(4 * M, 1.2, 1.3), q(9 * M, 0.0, 0.1)]  # last is invalid
    snaps = osp.snapshots(recs, 0, 11 * M)
    assert [s["t_ns"] for s in snaps] == [5 * M]           # 10m snapshot sees bid 0 → dropped
    assert snaps[0]["bid"] == 1.2 and snaps[0]["age_s"] == 60.0
