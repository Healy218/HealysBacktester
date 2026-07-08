# fa/collectors/edgar.py — Stage 0 collector: SEC EDGAR filing index.
"""Pull the daily EDGAR index for 10-K/10-Q/8-K/Form 4/S-1; archive metadata
(ts_utc, cik, ticker, form_type, accession, url). Document DOWNLOADS happen
lazily in Stage 3 scoring (per-filing-hash cache, scored exactly once) —
the collector only hoards the index. EDGAR is free; respect their rate limits
and set a proper User-Agent."""


def collect() -> int:
    raise NotImplementedError("FA Stage 0 — see FA_SPEC.md")
