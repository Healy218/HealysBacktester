"""Streamed market data for the live panel (2026-09-05).

Two daemons feed small on-disk stores that the scanners read instead of
polling REST each pass:
  * ``stock_stream``  — Alpaca SIP 1-minute bars for the panel's union
    universe → ``barstore`` (1m bars; 15m bars aggregated on read in exactly
    the shape the REST loader returns).
  * ``option_stream`` — Alpaca OPRA quotes for a dynamic contract set (the
    experts' recent alerts + open paper positions) → ``quotestore`` (latest
    NBBO per contract).
The stores are append-only parquet under ``nn_meta/live/feeds/data/`` and
are safe to read while written (atomic file replaces).
"""
