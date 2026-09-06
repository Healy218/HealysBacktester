# Data sources and time conventions

Current implementation reference, September 5, 2026. Provider entitlement and live availability must be checked in the target environment; repository code cannot guarantee them.

- **Underlying equities:** `data/vbt_data_loader.py` uses `vbt.AlpacaData` and local CSV caches. `data/alpaca_loader.py` and `v3/underlying.py` provide direct/history workflows. Credentials are read from the environment. There is no Yahoo Finance fallback.
- **Options:** `options/data/` combines cached Massive/Polygon contract metadata and bar files with provider access where configured. `v3/flatfiles.py` and `v3/derive_contracts.py` ingest/derive historical archives; `nn_meta/download_universe.py` refreshes them. Preserve old cache history: provider rolling entitlements can make old observations impossible to fetch again.
- **Point-in-time membership:** `nn_meta/universe_pit.py` freezes monthly membership from prior observations. v5/v6 use the historical union for acquisition and the monthly membership mask for research eligibility. A union by itself is not a PIT universe.
- **Sentiment/discovery:** `sentiment/` scores provider headlines; `fa/` archives social/news/filing observations. Availability is bounded by first capture, not merely the content's publication timestamp.

The legacy scanner requests fresh timestamp-bounded intraday bars, removes forming bars and rejects stale results. A provider failure is surfaced; it must not silently fall back to yesterday's signal. The bulk historical crawler's entitlement-compatible date cutoff is separate from this live request path.

OHLCV cleanup forward-fills from observed history and drops leading unavailable rows; it never backfills earlier bars using future prices. Alpaca data normalization converts aware timestamps to UTC before removing timezone metadata. Code consuming naive intraday indices must treat them as UTC.

Headline aggregates are right-labeled at the end of their observation bucket. Centered Elliott pivots become visible only when their right-hand confirmation window closes. Options marks distinguish bar-open fills from completed-bar close observations. These changes require rebuilding affected research artifacts; old numerical results are not automatically corrected by a code update.
