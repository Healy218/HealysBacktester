# V7 proposal-driven tick-feature demand

The earlier quote inventory selected contracts at every stock minute. The new
builder consumes the actual, PIT-filtered compact proposals and retains their
complete per-timeframe census. It shares selections across repeated strategy
decisions using symbol, decision clock, right and target DTE. All five targets
keep separate identities even when they select the same contract; future roll
paths can differ. Requests for identical contract/window pairs are shared.

`nn_meta/v7/entry_demand.py` uses a disk-backed SQLite index with bounded writes,
an explicit cache limit and disk reserve checks. Selection uses the latest
causally available raw minute price, at most 60 seconds old, and the existing
prior-date observed-chain selector. Missing raw prices and missing contracts
remain explicit selection statuses. New contracts first observed on the decision
date cannot enter the row. A security's dated ticker aliases remain distinct.

Each selected feature window requests both quote and trade observations from its
start minus the 30-second quote seed, bounded by the captured regular opening,
through the decision clock exclusively. These are the exact windows consumed by
the existing tick-feature engine. Separate targets and timeframes retain links
to those shared requests. No indicator or virtual strategy simulation is rerun.

`scripts/build_v7_entry_demand.py` verifies the active manifest/chain and all four
proposal stores. It exports immutable batches of at most 10,000 requests for the
existing shared-quota capture script. Each contract/day stays in one batch, so
separate exports cannot create overlapping capture shards for the same tape.
Code, runtime, parent payloads, declarations and receipts are bound and checked
again at completion; completed builds and exports resume without rescanning
the proposal stream.

## Verified real-data integration

AAPL, March 15–May 10, 2022; all 11,268 variants and 757,595 admitted proposals:

| Measurement | Result |
|---|---:|
| Distinct feature decisions, retaining timeframe | 19,702 |
| Shared selection decisions | 16,279 |
| Selected-contract records, all five targets | 81,395 |
| Links from selection/timeframe to feature windows | 197,020 |
| Distinct quote/trade feature requests | 55,126 |
| Contracts | 107 |
| Bounded export batches | 6 |
| Unioned capture intervals | 7,472 |
| Requested time per tape: quotes / trades | 603.15 hours each |

Every proposal's contribution was independently recounted from the parent
stores. An exhaustive eligible-contract calculation checked all 81,395 selections
using expiry distance, expiry, strike distance, strike and ticker tie ordering.
All stored raw prices and availability clocks matched the parent raw series.
All 197,020 feature links matched their exact causal scope. Every exported request
was present once, and the existing union function produced no duplicate or
overlapping capture ranges across batches.

Build: 28.03 seconds, peak RSS 429,828 KiB. Resume: 8.35 seconds, peak RSS
237,108 KiB, all 13 files unchanged. Output is 82,035,332 bytes, including the
63,922,176-byte SQLite index, source declarations and JSON capture batches.
This is a bounded integration measurement, not a full-universe storage forecast.
Full suite: 1,970 tests and 18 subtests passed, 18 warnings, 115.58 seconds.

Artifacts:

- `nn_meta/validation/v7-entry-demand-20260917`
- `nn_meta/validation/v7-entry-demand-exports-20260917`
- `nn_meta/validation/v7-entry-demand-verification-20260917`, receipt
  `0f2a0f8a2143a65edd74f221365610b417b54d56d10b8a4aeecd225e3a178e9c`

The verification artifact retains exact audit/command source, test/XML logs,
source and payload hashes, measured resources and the exhaustive results.

## Remaining execution and data work

These are **pre-decision feature requests**, not complete entry-fill, minute-mark,
exit, roll or physical-delivery coverage. No additional provider data was captured
in this milestone. Dated option-class hours and standard deliverable evidence
remain required before execution admission. Extend demand to those actual paths
and reconcile shared intervals before scheduling capture; do not treat a feature
capture as a resolved option outcome.

Daily/market context also remains unfinished. The captured SPY history has all
1,129 sessions, but 36 provider action records remain unresolved in the current
cash compiler, and the saved amount-publication matcher contains no SPY match.
Resolve that specific market-reference dependency alongside the full context
consumer; do not replace it with unadjusted returns or restart broad news capture.

The new readiness report `v7-readiness-20260917-entry-demand.json` still fails
the eight full-universe stages. No stage admission, training launch or V6 runtime
change is claimed by this work.
