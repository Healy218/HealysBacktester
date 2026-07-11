# tests/test_fa_trending.py
"""FA trending: entity extraction (cashtag + universe-aware bare tickers with
the ambiguity stoplist) and bull/bear lexicon — the pure logic that decides
what the morning report surfaces."""
from fa import trending


class TestTickerExtraction:
    def test_cashtags_always_win(self):
        assert "GME" in trending._tickers("yolo $gme calls")
        assert "SPCE" in trending._tickers("$SPCE to the moon")

    def test_bare_ticker_needs_universe_membership(self):
        # NVDA is in the universe and not ambiguous → matched bare
        assert "NVDA" in trending._tickers("NVDA earnings tomorrow")
        # ZZZZ is not a real ticker → never matched
        assert "ZZZZ" not in trending._tickers("ZZZZ moon")

    def test_ambiguous_bare_words_rejected(self):
        # these are real tickers but common words → cashtag-only
        out = trending._tickers("I love IT and USB is OPEN NOW")
        assert not ({"IT", "USB", "OPEN", "NOW"} & out)
        # but the cashtag form still resolves
        assert "USB" in trending._tickers("$USB broke out")

    def test_lowercase_bare_not_matched(self):
        # bare match requires uppercase (ticker-like); prose 'so' etc. ignored
        assert trending._tickers("i think it will go up so buy") == set()


class TestSentimentLexicon:
    def test_bull_and_bear_detected(self):
        assert trending._BULL.search("loading calls, this rockets")
        assert trending._BEAR.search("puts printing, this dumps")

    def test_neutral_text(self):
        t = "the company reported quarterly numbers today"
        assert not trending._BULL.search(t) and not trending._BEAR.search(t)
