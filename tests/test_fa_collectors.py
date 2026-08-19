# tests/test_fa_collectors.py
"""FA Stage 0: archive append/dedupe semantics and EDGAR index parsing —
the offline-testable core of the collectors."""
import pandas as pd
import pytest
import requests

from fa import archive, config
from fa.collectors import reddit
from fa.collectors.edgar import FORMS, parse_master_idx
from fa.collectors.reddit import _comment_rows, _post_rows


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


class TestStockTwitsSentiment:
    def test_counts_message_tags(self):
        from fa.collectors import stocktwits

        class _Sess:
            def get(self, url, **kw):
                class _R:
                    ok = True
                    def json(self):
                        return {"messages": [
                            {"entities": {"sentiment": {"basic": "Bullish"}}},
                            {"entities": {"sentiment": {"basic": "Bullish"}}},
                            {"entities": {"sentiment": {"basic": "Bearish"}}},
                            {"entities": {"sentiment": None}},   # untagged
                            {"entities": {}},                    # missing
                        ]}
                return _R()
        s = stocktwits._sentiment(_Sess(), "NVDA")
        assert s == {"bull": 2, "bear": 1, "n_msgs": 5}

    def test_equity_filter(self):
        from fa.collectors.stocktwits import _is_equity
        assert _is_equity("NVDA") and _is_equity("HD")
        assert not _is_equity("ETH.X")     # crypto
        assert not _is_equity("GBPUSD")    # forex pair (6 chars)
        assert not _is_equity("BRK.B")     # dotted class share


class TestRedditComments:
    def test_flattens_comment_stream(self):
        ts = pd.Timestamp("2026-07-08 21:00", tz="UTC")
        listing = {"data": {"children": [
            {"data": {"name": "t1_c1", "link_id": "t3_megathread",
                      "created_utc": 1783540900, "body": "$NVDA calls",
                      "score": 12}},
            {"data": {"name": "t1_c2"}},          # deleted body → skipped
        ]}}
        rows = _comment_rows(ts, "wallstreetbets", listing)
        assert len(rows) == 1
        assert rows[0]["comment_id"] == "t1_c1"
        assert rows[0]["link_id"] == "t3_megathread"


class _FakeResp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self.ok = status < 400
        self.headers = headers or {}
        self._payload = payload if payload is not None else {"data": {}}

    def json(self):
        return self._payload


class _FakeSession:
    """Replays a scripted list of responses and counts the calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, **kw):
        self.calls += 1
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class TestRedditRetry:
    """Reddit answers /new with sporadic 500s; one blip must not cost the run."""

    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch):
        monkeypatch.setattr(reddit.time, "sleep", lambda *_: None)

    def test_retries_500_then_succeeds(self):
        want = {"data": {"children": []}}
        s = _FakeSession([_FakeResp(500), _FakeResp(500), _FakeResp(200, want)])
        assert reddit._get_json(s, "u", {}, {}) == want
        assert s.calls == 3

    def test_gives_up_after_max_tries(self):
        s = _FakeSession([_FakeResp(500)] * reddit._MAX_TRIES)
        assert reddit._get_json(s, "u", {}, {}) is None
        assert s.calls == reddit._MAX_TRIES

    def test_does_not_retry_non_transient(self):
        s = _FakeSession([_FakeResp(403)])
        assert reddit._get_json(s, "u", {}, {}) is None
        assert s.calls == 1          # 403 is not worth a second try

    def test_retries_connection_error(self):
        want = {"data": {"children": []}}
        s = _FakeSession([requests.ConnectionError("boom"),
                          _FakeResp(200, want)])
        assert reddit._get_json(s, "u", {}, {}) == want

    def test_honours_retry_after(self, monkeypatch):
        waits = []
        monkeypatch.setattr(reddit.time, "sleep", waits.append)
        s = _FakeSession([_FakeResp(429, headers={"Retry-After": "7"}),
                          _FakeResp(200, {"data": {}})])
        reddit._get_json(s, "u", {}, {})
        assert waits == [7.0]

    def test_total_wipeout_raises_not_silent_zero(self, tmp_archive, monkeypatch):
        """A dead source must reach fa.collect as a failure, not as +0 rows."""
        monkeypatch.setattr(reddit, "_token", lambda _s: "tok")
        monkeypatch.setattr(reddit.config, "SUBREDDITS", ["options"])
        monkeypatch.setattr(reddit, "_get_json", lambda *a, **k: None)
        with pytest.raises(RuntimeError, match="every listing failed"):
            reddit.collect()

    def test_one_bad_sub_still_archives_the_others(self, tmp_archive, monkeypatch):
        monkeypatch.setattr(reddit, "_token", lambda _s: "tok")
        monkeypatch.setattr(reddit.config, "SUBREDDITS", ["dead", "alive"])
        good = {"data": {"children": [
            {"data": {"name": "t3_ok", "created_utc": 1751925600,
                      "title": "hi", "selftext": "", "score": 1,
                      "num_comments": 0, "permalink": "/r/alive/ok"}}]}}

        def fake_get(_s, url, *a, **k):
            if "dead" in url:
                return None
            return good if url.endswith("/new") else {"data": {}}

        monkeypatch.setattr(reddit, "_get_json", fake_get)
        assert reddit.collect() == 1          # the live sub's post survived
