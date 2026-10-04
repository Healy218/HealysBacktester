# ETFE fresh Alpaca acquisition — October 3 successor

The user's follow-up directs a fresh Alpaca-only ETFE build and continued stock
and option downloading. This changes acquisition ordering in the earlier
[source contract](ETFE_CONTRACT_20261003.md) and
[acquisition declaration](ETFE_ACQUISITION_20261003.md): unresolved source facts
do not block implementing and running bounded fresh raw downloads. They remain
visible at the point where features, execution or data admission need them.
Earlier frozen declarations and their evidence retain their original meaning.

## Scope and data ownership

SPY/QQQ/VOO, 1/5/15-minute signals, the accepted strategy/risk specifications and
completed one-minute option VWAP remain. Download stock and option observations
from Alpaca into `nn_meta/data_cache_etfe/` only. No previous-project metadata,
cached bars, feature arrays, labels, schema artifacts, checkpoints or models are
data inputs. Reusing a mathematical strategy specification is not reusing its
old dataset. Rebuild features, eligibility, labels and models for these inputs.

Alpaca contract listings are freshly fetched **symbol-discovery responses**.
Retain their native fields without using current status, OI, multiplier or
deliverables as a historical feature or execution rule. Do not repair old project
metadata or require that repair before downloading prices. Dated terms needed
for later execution remain a separate validation responsibility.

## History and source semantics

The desired final window is still Alpaca's available options history for these
three ETFs through October 2, 2026 inclusive (exclusive UTC end October 3 04:00).
Replace the earlier provider-global-history prerequisite with a **scoped ETFE
coverage census**. No need to prove the earliest event in unrelated symbols.
Earliest observed, usable and verified-complete coverage are separate fields.
January 18, 2024 remains an observed lead, not a newly asserted exact floor.
Earlier catalogue/price discovery stays pending; no silent left truncation.

Stock bars use explicit SIP, raw adjustment and `asof=-` so historical symbol
mapping is not silently applied. Option bars/trades use the public historical
routes without a feed parameter. Label source as Alpaca historical option bars
or trades, preserving route/version; do not pretend to have received an explicit
trade-feed identifier. OPRA bar evidence and trade-feed uncertainty remain dated
source notes. No indicative latest-data substitute or historical option quotes.

## Initial bounded download milestone — ETFE-1.bootstrap

Prepare a fresh source-bound plan for six stock partitions: all January 2024
and October 1–2, 2026, separately for each ETF. January 1 is collection padding
before the observed lead, not the admitted research start or permission to use
extra warmup. Fetch both current statuses of the January 19, 2024 and October 2,
2026 option expiries, both rights and all returned strikes: twelve discovery
partitions. Complete every page, recording terminal empty responses separately.

From only those new responses, prepare a second immutable plan. For January 18,
2024 and October 2, 2026, select the nearest strike to the fresh 09:30 stock-bar
open, separately for calls and puts (symbol breaks ties). Fetch full civil-day
option minute bars and opening 30-minute trades: twelve partitions, twelve
sample contracts. This deterministic choice exercises transport and reader
behavior; it is **not** point-in-time candidate eligibility or the production
chain-selection rule. No profitability-based sample selection.

Completion: both plans' page chains reach terminal tokens, hashes/identities
verify, raw rows retain exact timestamps and per-page occurrence lineage, and
an interrupted download resumes without changing committed pages. Empty data
stays `empty_response`, not demonstrated no-trade coverage. Report actual bytes,
requests, page/row counts, timestamp bounds, ordering and resource use. Download
completion does not close ETFE-0, ETFE-1.freeze or the integrated ETFE-4.pilot.

## Transport and resources

One serial request stream, capped at 60 requests/minute, no worker pool. Parallel
feature/build work later uses `scripts/lib/autosize.sh`. Per invocation: at most
128 GETs and 30 minutes. Per plan root: 512 MiB, including raw attempts and source
snapshots; maximum page 32 MiB. Keep disk free >=max(100 GiB,20% filesystem), and
RAM available >=max(2 GiB,20% physical RAM) plus parsing allowance. No swap budget.
These are bootstrap ceilings, not a forecast for full acquisition.

Persist body and sanitized response receipt before publishing the committed
page pointer; fsync and exclusive publication prevent partial pages appearing
complete. A nonblocking file lock excludes concurrent writers. Resume verifies
all prior page hashes, parameters and tokens before issuing another GET. Persist
failed attempts; transient network/429/5xx errors receive up to five attempts per
page in one invocation with 1/2/4/8-second backoff. Honor Retry-After/rate-reset
headers; waits exceeding 60 seconds stop for later resumption. A capped run
remains incomplete. Schema drift, repeated tokens, source changes and corrupted
committed pages fail closed. Changed capture code requires a successor plan.

Raw pages and failed attempts are immutable. Mutable orchestration consists
only of the writer lock; run audits are uniquely named. Preserve no-ID trades as
individual occurrences, including identical prints. Use integer nanosecond
timestamp comparisons and inclusive provider end = exclusive end minus 1 ns.
No normalization replaces or fabricates prices, quotes, economic multipliers,
publication times or missing observations. Full normalization/quality/coverage
and integrated feature/execution resource measurement follow this bootstrap.

## Remaining gates

ETFE-0's four definitions remain declared; source admission is not claimed.
H1 becomes scoped coverage work during acquisition. R1/R2 apply to historical
eligibility/execution, not permission to store raw responses. P1 remains source
provenance work, not a reason to retry unsupported feed parameters. Advance the
fresh acquisition/normalization and integrated pilot components while preserving
all scientific checks required before input/dataset freeze and training.

Full-history download budgets must follow measured bootstrap demand and the
broader integrated pilot; do not extrapolate option storage from ticker count.
This change does not authorize an unbounded bulk campaign or deploy an expert.
