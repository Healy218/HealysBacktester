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

Daily snapshots cover the tracked 300-symbol liquid discovery universe:
legacy quarterly financial statements, short interest/days-to-cover, short-sale
volume and float. Eight-K disclosures are captured market-wide over seven days.
Empty coverage (e.g. financial statements for an ETF) is distinct from failed
requests. New paid Financials/Ratio endpoints and Benzinga add-ons are not used.
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

Pending live deployment/verification in this implementation session.
Planned additions: hourly news (:05 UTC), daily fundamentals (23:10 UTC),
daily immutable features (01:40 UTC), weekly evaluation (Sunday 02:00 UTC).
Use the existing job-receipt wrapper and resource limits. Source-specific
health and aggregate job checks expose partial failures.
