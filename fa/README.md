# fa — ticker discovery pipeline

Collectors, entity resolution, attention scores, monthly ranking and forward
tracking are implemented. The fundamental overlay (`overlay.py`) remains a
scaffold. Design: `../docs/specs/FA_SPEC.md`.

| Stage | Module | Purpose |
|---|---|---|
| 0 | `collectors/` | Reddit, StockTwits, news and EDGAR captures |
| 1 | `entities.py` | Cashtag/name resolution |
| 2 | `scores.py` | Attention velocity against trailing baseline |
| 3 | `overlay.py` | Fundamental overlay scaffold |
| 4 | `ranker.py` | Corroborated monthly Top-10 |
| 5 | `tracker.py` | Forward excess returns and cohort graduation |

`python -m fa.collect` runs available collectors once. Reddit requires API
credentials. Archives partition by capture month; updates serialize per source,
write to a temporary parquet, and atomically replace the month file. Previously
observed identities are excluded across all partitions. Existing cross-month
duplicates are also removed when rankings load the archive.

Historical ranking cutoffs refer to **first capture in UTC**, not provider
publication time. Captures after the exact cutoff are removed before daily
aggregation; each daily score becomes available at its last included capture.
The default ranking window is the trailing 31 calendar days, while velocity
normalization retains its own trailing 90-day baseline. Corroboration applies
within that ranking window. `--prior-month` uses the instant before the new
month starts; an explicit `--as-of YYYY-MM-DD` means midnight at that date.
Ticker tags are split individually, and both monthly ranking and daily trending
filter resolved tickers to their respective configured liquidity universes.

Frozen rankings remain write-once. The existing August 2026 artifact predates
the capture-time correction and is historical evidence, not a corrected
point-in-time benchmark. Do not overwrite it or count its returns as validation
of the corrected ranker. New rankings must use the corrected path.
New freezes carry `recipe_version=capture-cutoff-trailing31-v1`. The tracker
warns and excludes unversioned or stale recipes from the prospective scoreboard
and its graduation input. The August artifact no longer counts toward the
three valid monthly rankings required for validation; retain it unchanged.

Forward returns normalize timestamps to naive UTC. Graduation joins each
return to the same `(ticker, ranking_date)` cohort that passed probation;
a later winning pick cannot rescue an earlier losing cohort. Daily StockTwits
sentiment is explicitly **snapshot-weighted**: overlapping hourly windows can
contain the same messages, so the total is not a unique-message count.
