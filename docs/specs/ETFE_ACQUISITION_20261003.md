# ETFE acquisition and bounded pilot contract

This declares ETFE-0.acquisition-design. It derives demand from the
[feature](ETFE_FEATURES_20261003.md), [execution](ETFE_EXECUTION_20261003.md)
and [evaluation](ETFE_EVALUATION_20261003.md) contracts. It is a workload design,
not an acquisition run or a measured resource forecast. Resolve H1/R1/R2/P1 in
the [source contract](ETFE_CONTRACT_20261003.md) before the integrated pilot.

## Required inputs and feasible routes

| Input | Demand and source | Admission evidence |
| --- | --- | --- |
| SPY/QQQ/VOO underlying OHLCV | Alpaca `/v2/stocks/bars`, 1Min, SIP, raw; all regular sessions from verified start through October 2 | Full pagination, timestamps, missing-minute classification, corporate-action reconstruction |
| Underlying quotes | Alpaca `/v2/stocks/quotes`, SIP, around expiry classification, exercise delivery and all held-stock marks/liquidation | Observed bid/ask, size units, timestamps, identity, complete demand windows |
| Option execution bars | Alpaca `/v1beta1/options/bars`, 1Min; union of feature/entry/holding/exit/roll contracts/windows | VWAP/volume/count schema, OPRA source statement, gaps, revision vintage, no synthetic fallback |
| Option trades | Alpaca `/v1beta1/options/trades`; causal feature windows and pilot bar reconciliation | Complete pages, native IDs/order/conditions, positive prices/sizes, P1 source semantics |
| Daily option context | Same bar route; all rights/strikes in 1–45 DTE, full-session volume and final stock-close surface reference | Complete historical discovery inventory, dated reference eligibility, daily coverage and valid no-trade records |
| Discovery records | Alpaca `/v2/options/contracts`, both statuses with explicit expiry bounds and `show_deliverables=true` | Current records only; never historical-chain proof |
| Historical existence and contract terms | Prior-date Alpaca trades/bars plus effective OCC/exchange records, adjustments and official expiration references | R1: dated strike/multiplier/deliverable/exercise identity; observed contracts are a conservative subset, not the full listed chain |
| Calendar and class hours | Alpaca stock calendar plus dated exchange class/expiration/early-close notices and OCC settlement calendar | R2: explicit effective intervals and historical exceptions |
| Actions and ETF identity | Dated issuer/OCC/exchange documents and Alpaca corporate-action records where available | Effective time, announcement/available time, source bytes and symbol linkage; no current adjusted-price shortcut |

No external options price provider, historical option quote route, current option
IV/Greeks snapshot, archived V7 prices or implicit Yahoo/FRED inputs are used.
Fixed-rate IV is a declared proxy, so it does not create hidden rate/dividend
forecast data requirements. Actual corporate distributions still need dated
evidence for price units/contract adjustments. References may come from official
issuers/exchanges/OCC; the Alpaca-only restriction governs options market data.

## Discovery and demand generation

Generate the entire SPY/QQQ/VOO candidate census from the frozen catalog,
including both permitted directions and dated DTE eligibility. Do not first
choose profitable variants. Deduplicate capture by source/contract/time interval,
with a many-to-many mapping back to every logical proposal and purpose.

R1 requires a complete discovery mechanism for the needed 1–45 DTE contracts.
Current inactive/active catalogs are a starting symbol list, not proof that
deleted or transformed historical symbols are absent. Cross-check dated official
series/adjustment records. Establish earliest observations per discovered series;
only prior-date observations make it eligible for causal selection. Retain
unobserved-listed, first-day and transformed contracts in the audit census.
Failure to reconcile this universe blocks daily surface completeness and chain
selection; a sample of near-money symbols cannot replace it.

Phase A collects dated calendars/identities, raw underlying minutes and daily
surface inventory. Phase B computes causal candidate selection and exact option
feature/entry demand. Phase C traverses holding/exit/roll/physical paths to a
terminal or censored disposition, acquiring newly required intervals. Neither
missing pages nor a request budget exhausted at a frontier is a terminal
strategy outcome. Freeze only after all required demand edges have receipts.
Preserve full 1–45 DTE surface demand even though purchases use 1–9 DTE.

## Partition and transport protocol

Partition raw observations by provider/feed/kind/security/contract/session;
chunk busy trade/quote sessions into 30-minute windows and split further when
needed. Stock bars may use symbol/month partitions but retain session coverage.
Use internal half-open [start,end), API inclusive end=end-1ns, UTC int64
nanoseconds, explicit 1Min and sort=asc. Batch at most 100 option symbols where
supported. Limits apply to the entire response, not each symbol; pagination
must continue to null token even after a short or empty page.
[Alpaca trade pagination](https://docs.alpaca.markets/us/reference/optiontrades).

Each immutable raw request records URL/query without credentials, API version,
account role/entitlement evidence ID, feed basis, request/response time, status,
safe rate-limit/request-ID headers, token-in/out, body byte count/SHA256 and
capture/source/config hash. Keep native fields and timestamp strings as well as
parsed ns. Secrets remain in root .env, with only the exact credential pairs
read; never export unrelated campaign selectors or log headers containing keys.

Use a persistent request inventory (SQLite/WAL or equivalent) with keys covering
source, feed, contract set, interval, kind, normalization/condition policy and
contract hash. States: planned, running, retry_wait, captured, normalized,
verified, quarantined. Page chains are append-only. Persist page bytes and hash
before atomically committing the next-token checkpoint; terminal verified state
requires checksum, ordering, duplicate and demand reconciliation. Restart checks
the saved page before advancing. Repeated tokens, mismatched parameters or
conflicting keys stop that partition; a capped page count never means complete.

Bound rate to min(documented entitlement, observed headers, **60 GET/minute**)
for the pilot, one in-flight request per rate budget. Missing rate headers keep
the conservative cap. Honor Retry-After; for 429/5xx/network failures use at most
five attempts with 1/2/4/8/16-second base delays and seeded bounded jitter.
401/403 stop immediately; 404 is unsupported/missing resource, never no trades.
Return unfinished inventory after exhaustion. Limit a streamed page to 32 MiB,
split requests on overflow and retain failure receipts.

Deduplicate exact bars by (contract,interval start,timeframe); conflicting
values are revisions with separate immutable vintages. Retained Alpaca trade
samples have c/p/s/t/x and **no native trade ID**. Preserve every occurrence in
one complete page chain, with a capture identity (request ID, page ordinal, row
ordinal), explicitly not an exchange trade ID. Replay a committed page once;
never content-deduplicate equal-time/equal-size prints. Nonoverlapping intervals
prevent cross-partition duplication. Changed pages or inconsistent boundaries
quarantine the entire chain; recapture as a new vintage rather than joining
pieces of two downloads. No absent correction history is fabricated. Freeze a
chosen final-vintage partition as of capture time with a revision ledger;
reacquisition creates a successor, never overwrites the input freeze.

## Missingness and full coverage

Every expected key has one disposition: observed_valid, observed_invalid,
complete_no_trade, outside_session, not_yet_eligible, warmup_unavailable,
transport_incomplete, provider_gap, reference_unresolved, or boundary_censored.
An empty HTTP 200 page only establishes `empty_response` until all pages,
contract existence, session and provider-health controls reconcile. Historical
provider omissions cannot always be distinguished from inactivity: preserve
`provider_gap` when evidence is insufficient, especially VOO and market-wide
simultaneous gaps. Do not manufacture no-trade status to fill a minute grid.

Coverage summaries include raw count/bytes, minimum/maximum timestamps, page
census, duplicate/correction counts, expected vs observed sessions, first usable
per feature and reason-coded missingness by ticker/date/contract. Logical
candidate = eligible + all explicitly excluded/unresolved dispositions;
physical factorization must reproduce that identity. Report at least the
documented suspected morning gaps on 2024-02-26 and 2024-03-15 as audit windows,
without assuming a forum report proves absence in this capture.

## Bounded ETFE-4 pilot workload

No pilot was executed here. Once the source gate closes, measure these fixed
strata, selected for market structure/calendar rather than outcomes:

| Dates | Required observations |
| --- | --- |
| 2024-01-18–19 | Boundary lead and first short expiries, all three ETFs; omit only if provider floor proves outside scope, with recorded reason |
| 2024-02-26, 2024-03-15 | Suspected provider morning gaps and expiry context |
| 2024-05-24, 2024-05-28–31 | Settlement transition and holiday delivery mechanics |
| 2024-11-29 | Early-close alignment and last executable bars |
| 2025-04-04, 2025-04-07 | Busy-market throughput for SPY/QQQ; sparse VOO contrast |
| 2026-10-01–02 | Fixed end, unresolved horizons and no next-session data |

For each session, include open/close 30-minute windows and noon 30 minutes,
nearest eligible call/put for every DTE target, prior-date existence evidence,
all required prior feature context and full-day daily surfaces. Include full-day
holding data when a sampled proposal needs it; stop at the user's fixed boundary.
First enumerate request counts before executing. Deduplicate identical contracts
across targets. Generate all 20 families and 1/5/15m signals on the pilot input;
for execution select at most two proposals per family/ticker/timeframe per
session by smallest SHA256(proposal ID), never by return. Zero-proposal strata
are reported, not replaced after inspecting outcomes.

Retain source-native lookback/state warmup. Include one streaming full-prefix
feature shard for a ticker/timeframe to measure state growth beyond a short
window. Small fixtures are sufficient for rare roll/physical-delivery mechanics
when no natural case is present, but cannot establish real-data coverage or
execution parity. Fit the 21 configurations once on a chronological pilot
train/validation slice with no threshold search; pilot metrics are diagnostic,
not final acceptance, and cannot change the final trial search.

Hard pilot ceilings: 10,000 GETs, 20 GiB new total storage (raw, normalized,
temporary files, source snapshots, checkpoints and a verified second copy),
and six hours elapsed. These are **stop limits**, not promises that the workload
fits. Preserve unfinished partitions; a limit stop yields incomplete pilot.
At launch record current free disk and RAM. Preserve free disk >=max(100 GiB,
20% filesystem capacity), memory reserve >=max(2 GiB,20% physical RAM), and no
swap-as-capacity. If reserve plus one worker does not fit, launch none even
though the shared autosizer has a floor of one.

Use `scripts/lib/autosize.sh` with measured peak-per-worker times 1.25, numerical
threads=1 and explicit memory/disk guards. Clear inherited OMP limits only in
the sizing subprocess as documented. Measure one task at a time initially;
concurrency is computed from evidence, not a hardcoded worker count. Stop on
reserve breach, repeated rate-limit failure, unrecognized references, schema
drift or hash failure. Do not reclaim unrelated artifacts or assume MRHA space.

Measure GET/page counts, bytes/event, compressed/raw/temporary/freezes footprint,
peak RSS, peak model-fit memory, throughput by stratum, queue overhead and
checkpoint/restore size. Forecast full-scope low/base/high demand using the
enumerated actual contract/session/proposal census and measured rates, including
surface discovery and chained rolls. Do not extrapolate from ticker count alone.
Interrupt after a committed page and dataset shard; resumed hashes, row census
and predictions must match uninterrupted output. Final ETFE-4.admission later
reconciles these forecasts against actual full-build measurements.
