# tests/test_fa_collectors.py
"""FA Stage 0: archive append/dedupe semantics and EDGAR index parsing —
the offline-testable core of the collectors."""
import pandas as pd
import pytest

from fa import archive, config
from fa.collectors.edgar import FORMS, parse_master_idx
from fa.collectors.reddit import _post_rows


@pytest.fixture
def tmp_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE", tmp_path)
    return tmp_path


def _rows(ts, symbols):
    return pd.DataFrame([{"ts_utc": ts, "symbol": s, "rank": i + 1}
                         for i, s in enumerate(symbols)])


class TestArchive:
    def test_append_and_dedupe(self, tmp_archive):
        ts = pd.Timestamp("2026-07-08 14:00", tz="UTC")
        n1 = archive.append("src", _rows(ts, ["AAA", "BBB"]),
                            key=["ts_utc", "symbol"])
        assert n1 == 2
        # exact rerun adds nothing
        n2 = archive.append("src", _rows(ts, ["AAA", "BBB"]),
                            key=["ts_utc", "symbol"])
        assert n2 == 0
        # later snapshot of the same symbols is new data, not a duplicate
        later = ts + pd.Timedelta(hours=1)
        assert archive.append("src", _rows(later, ["AAA"]),
                              key=["ts_utc", "symbol"]) == 1
        stored = pd.read_parquet(tmp_archive / "src" / "2026-07.parquet")
        assert len(stored) == 3

    def test_empty_frame_is_noop(self, tmp_archive):
        assert archive.append("src", pd.DataFrame(), key=["x"]) == 0
        assert not (tmp_archive / "src").exists()

    def test_partitions_by_month(self, tmp_archive):
        df = _rows(pd.Timestamp("2026-07-31 23:59", tz="UTC"), ["AAA"])
        df2 = _rows(pd.Timestamp("2026-08-01 00:01", tz="UTC"), ["AAA"])
        archive.append("src", pd.concat([df, df2]), key=["ts_utc", "symbol"])
        assert (tmp_archive / "src" / "2026-07.parquet").exists()
        assert (tmp_archive / "src" / "2026-08.parquet").exists()


_IDX = """Description:           Master Index of EDGAR Dissemination Feed
Last Data Received:    July 8, 2026

CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
1000045|NICHOLAS FINANCIAL INC|10-K|2026-07-08|edgar/data/1000045/0001.txt
1000045|NICHOLAS FINANCIAL INC|4|2026-07-08|edgar/data/1000045/0002.txt
1000229|CORE LABORATORIES N V|13F-HR|2026-07-08|edgar/data/1000229/0003.txt
1000230|SOME CO|8-K|2026-07-08|edgar/data/1000230/0004.txt
"""


class TestEdgarParse:
    def test_parses_wanted_forms_only(self):
        df = parse_master_idx(_IDX)
        assert set(df["form_type"]) == {"10-K", "4", "8-K"}
        assert len(df) == 3                      # 13F-HR filtered out
        assert df.iloc[0]["cik"] == "1000045"
        assert df.iloc[0]["path"].startswith("edgar/data/")

    def test_headers_and_junk_ignored(self):
        assert parse_master_idx("no pipes here\n\n").empty
        assert "13F-HR" not in FORMS


class TestRedditParse:
    def test_flattens_listing(self):
        ts = pd.Timestamp("2026-07-08 20:00", tz="UTC")
        listing = {"data": {"children": [
            {"data": {"name": "t3_abc", "created_utc": 1751925600,
                      "title": "YOLO $GME", "selftext": "x" * 9000,
                      "score": 42, "num_comments": 7,
                      "permalink": "/r/wsb/abc"}},
            {"data": {}},                       # malformed child ignored
        ]}}
        rows = _post_rows(ts, "wallstreetbets", listing)
        assert len(rows) == 1
        assert rows[0]["post_id"] == "t3_abc"
        assert len(rows[0]["selftext"]) == 5000  # capped
        assert rows[0]["subreddit"] == "wallstreetbets"

    def test_empty_listing(self):
        assert _post_rows(pd.Timestamp.now(tz="UTC"), "stocks", {}) == []
