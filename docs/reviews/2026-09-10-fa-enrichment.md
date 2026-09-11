# FA enrichment and experimental evaluation

User authorized work on (1) news capture, (2) fundamentals/events/positioning,
(3) immutable timestamped features and (4) evaluation against a baseline.
This work lives on `ops/fa-automation-20260910`, with durable runtime
`/home/healy/Coding/HealysAutomation`. Main campaign source stays pinned.

## Data and collector contracts

`fa/enrichment.py` uses existing Alpaca and Massive credentials. No new
subscription or OpenAI API usage. Separate news collectors use full pagination,
bounded retries, same-provider pagination validation, HTTP error receipts and
independent checkpoints. Requests overlap two days after the initial seven-day
capture. Checkpoints advance only after all pages complete. This is a bounded
recent-news capture, not a claim to discover every old article revision.

Alpaca archives include available article content but no fabricated sentiment.
Massive archives include ticker-specific provider sentiment and reasoning.
Raw payload revisions are hashed and retain their observation times; repeated
unchanged responses are suppressed, while A -> B -> A transitions are retained.
Articles fetched today with older publication dates are still first observed
today. Provider sentiment is explicitly labeled unversioned; captured outputs
are preserved rather than recomputed silently.

Daily captures cover the tracked 300-symbol liquid discovery universe:
legacy quarterly financial statements, short interest/days-to-cover, short-sale
volume and float. Eight-K disclosures are captured market-wide over seven days.
Empty coverage (e.g. financial statements for an ETF) is distinct from failed
requests. Positioning uses market-wide pages: short interest over 35 days,
short volume over seven days, and latest available float. Date-plus-ticker sort
prevents pagination from skipping tickers tied on a reporting date. One float
record without its optional ticker is counted as unmappable. Requests are paced;
HTTP 429 without Retry-After backs off 60 then 120 seconds. Successful same-day
financial captures are reused during partial retries, preserving their timestamps. New paid Financials/Ratio endpoints and Benzinga add-ons are not used.
Reddit remains outside this new feature/training path.

Official schemas checked:
- https://massive.com/docs/rest/stocks/news
- https://massive.com/docs/rest/stocks/overview
- https://docs.alpaca.markets/us/reference/news-3
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## Feature contract

`fa/feature_snapshots.py` selects only records captured by the cutoff and the
latest revision then available. It also excludes future publication/filing
and reporting dates. Exact URL or normalized headline/date matches collapse
syndicated copies into one story; all distributors remain one news family.
Ticker aliases apply to articles and ticker-specific sentiment consistently.
Sentiment categories map positive/neutral/negative to +1/0/-1; missing sentiment
remains missing. This mapping is not a calibrated return probability.

Features: seven-day unique news count, sentiment and sentiment coverage;
year-over-year same-quarter revenue growth and share dilution; gross/net
margins, operating-cash/revenue, liabilities/assets, current ratio; days to
cover, short interest, short-sale volume ratio and float percentage; unique
filing and disclosure-category counts. Technical baseline features are 5/20
session returns and 20-session volatility using completed price dates before
the cutoff's UTC day. Price coverage remains the existing validated baseline
plus frozen cohort picks; 300-symbol FA coverage does not imply 300 price files.

Snapshots preserve features, row evidence, raw/price hashes, code hashes and
nonmissing coverage counts. Fresh successful collector and price jobs are
required. No current live thresholds or official monthly ranking weights are
changed by the experiment. Monthly snapshots preserve the new raw archives,
but the existing attention-ranking recipe does not automatically consume the
new feature weights or promote candidates.

## Evaluation contract

`fa/evaluate_features.py` compares a fixed ridge technical baseline with four
individual FA feature groups and all groups together. It uses train-only
imputation/scaling with missingness indicators. Expanding chronological folds
purge training observations whose return labels were not known before the
first test cutoff. Intraday duplicate observations collapse to one per ticker
per capture day. Every variant uses identical eligible rows.

Target: return from the next session close to the fifth subsequent session
close. Defaults require 40 distinct training sessions and 10 out-of-sample
sessions. Reports include MAE, direction accuracy and daily cross-sectional
rank correlation. These are forecast diagnostics, not costed strategy P&L,
statistical significance, or permission to promote a model. No historical FA
snapshots are fabricated from today's captures. With no matured forward labels,
the report must explicitly say awaiting-forward-outcomes and contain no
performance metrics. Real comparative evidence requires collecting forward.

## Runtime schedule and verification

Source deployed to the isolated runtime through `94ba6b2`. Additions: hourly news (:05 UTC), daily fundamentals (23:10 UTC),
daily immutable features (01:40 UTC), weekly evaluation (Sunday 02:00 UTC).
Use the existing job-receipt wrapper and resource limits. Source-specific
health and aggregate job checks expose partial failures.


Verification on September 11 UTC (September 10 Chicago): full suite 1,498 tests
and 18 subtests passed before final provider schema corrections; 29 focused
FA capture/runtime tests passed after those corrections. Live bulk capture:
financials 232/300 (68 valid empty responses), short interest 300/300 (45,047
provider rows), short volume 300/300 (61,267 provider rows), float 228/300
(72 empty; 6,838 provider rows, one unmappable record). Earlier partial HTTP 429
runs were not accepted as healthy input. Bulk pagination corrections superseded
the incomplete date-only sorted captures before any feature snapshot was created.

First immutable snapshot: `fa/artifacts/enrichment/20260911T034526761094Z`.
It contains 300 feature rows and 3,800 deduplicated news stories; sentiment
available for 215 symbols, same-quarter revenue growth for 202, and technical
baseline features for 120. Missing feature values remain missing.
First report: `fa/artifacts/enrichment_reports/20260911T034528646388Z.json`,
status `awaiting-forward-outcomes`, zero labeled rows, no performance metrics.
All four new user timers enabled; first news/fundamentals/features/evaluate
and aggregate health receipts succeeded by 03:45:29 UTC. Daily collection
builds an honest forward dataset for month-end review; the default 40 training
plus 10 test sessions cannot be accumulated by this month's end.

The original 7.2 GB packed backup, restore and dependent activation health
check completed successfully on September 10 at 20:06:44–20:06:46 UTC.
