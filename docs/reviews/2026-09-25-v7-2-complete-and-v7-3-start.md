# V7-2 complete; V7-3 started — September 25, 2026

## Completed gate

V7-1 and V7-2 are complete. V7-3 is now the active stage. The existing 591-security,
1,773-store 5/15/30 proposal catalog is retained unchanged; its full deep audit
and historical-loader equivalence remain the controlling catalog evidence.

The missing daily/market context was built alongside it at
`nn_meta/validation/v7-daily-context-20260925-full`: 591 securities × 1,129
source sessions = 667,239 rows, March 15, 2022–September 14, 2026.
564,453 history sessions are admitted by the exact frozen proposal routing.
Every admitted surface selection matched the selected stock ticker, observed
minute count, raw close and captured availability. SPY supplies market context.
Reviewed actions, identity boundaries and dated sector records are retained.
Excluded histories and unobserved surfaces remain missing; nothing is forward-filled.

The independent persisted-data audit reopened all shards and checked receipt,
input and source hashes, security/date uniqueness, all ten daily fields,
raw-close action returns, rolling volatility, beta, term slope, IV change,
next-open availability, sector joins and reported missingness. Two raw-input
prefix replays per security (90 and 565 sessions) passed: 1,182 replays.
The first audit attempt used an incorrect raw-history clock expectation;
inspection confirmed raw facts use session close and model context uses next
open. The check was corrected; no saved daily artifact changed.

Six securities lack enough usable history for a 60-session beta. Five lack
21-session realized volatility. These explicit warmups are retained. Surface
missingness remains material and is quantified per security/feature in the
summary, rather than filled or hidden. The 4,422 daily action references are
counted on the frozen history path; this is a different census from the
catalog's 4,314 coverage/preflight events. Full option-tick row integration
awaits the real V7-3 captures. No training readiness or performance verdict is implied.

The new completion receipt is
`nn_meta/validation/v7-2-completion-20260925/complete.json` and its gate is
`gate.json`. It binds the original catalog checkpoint and
`nn_meta/validation/v7-2-full-daily-audit-20260925.json` plus the new daily
summary receipt. The original `v7-2-final-deep-gate-20260925.json` remains an
immutable earlier checkpoint showing the then-missing daily context; do not
rewrite it, because the new daily inputs bind its hash.

## Actual V7-3 work completed

The first measured entry-demand run consumed MTUM (`BBG004FPTZB8`), selected
as a small current-loader example from the completed 591-security scope.
It processed all 8,451 variants and 29,843 admitted proposals across 5/15/30.

- 1,319 distinct timeframe decisions; 1,021 contract-selection decisions.
- Five target identities per selection decision: 5,030 selected and 75 with
  no fresh stock price. Missing-price cases create no fabricated contract.
- 3,552 requests: 1,776 quote and 1,776 trade requests, across 76 contracts.
- One immutable export batch; about 11.0 MB total demand/export footprint.
- SQLite integrity, proposal/selection census, request intervals, links and
  exported payload hashes passed.

Demand: `nn_meta/validation/v7-3-entry-demand-20260925/BBG004FPTZB8`.
Export: `nn_meta/validation/v7-3-entry-requests-20260925/BBG004FPTZB8`.
Launch receipt: `nn_meta/validation/v7-3-launch-20260925`.
No provider downloads were made by this pilot. Its scope is pre-decision
feature windows. Entry fills, minute marks, exits, rolls, delivery windows,
dated option hours and standard contract references remain V7-3 work.
The full scope is still all 591 securities; this small pilot is not a new universe.

## Next active work and operation

Implement a resumable all-security entry-demand scheduler, preserving the
415+10 historical-loader equivalence proofs without changing frozen receipts.
The strict demand reader was exercised on current-loader MTUM; historical
stores require an explicit proof-aware consumer before scheduling all 591.
Reconcile the full request union and forecast volume before capture expansion.
Keep at most four capture workers, one inner thread, the 100 GiB disk reserve
and 250 GB acquisition ceiling. Do not extrapolate this small sparse pilot
into a full-build ETA or full-universe download estimate.

The catalog controller has completed; do not restart it. The daily build and
first entry-demand pilot have also completed, so there is no background build
from this session. The old catalog progress CLI correctly remains at 1,773/1,773;
it is not a V7-3 progress meter. A scheduler must publish its own progress.

Validation: 19 focused daily tests; full suite 2,401 tests and 18 subtests
passed, with 20 warnings. About 344.5 GB free remained after the audit.
