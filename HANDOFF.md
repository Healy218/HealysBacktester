# V6 blocked by provider context; V7 base acquisition nearly complete

Updated 2026-09-15T15:15:47.729000+00:00.

## Immediate continuation

1. V6 remains degraded: MASSIVE September 14 minute file is missing. The three
   morning refreshes failed; pointer through September 11. Entries and ordinary
   strategy exits are blocked; expiry fallback remains active and latest pass
   reported no fallback errors. Do not claim recovery from timer success.
2. Newly installed `healys-v6-context-retry.timer` checks weekdays at :08/:38
   UTC from 09 through 19 hours. Separate main-checkout helper checks all missing
   sessions, then requests existing refresh only when files exist and producer/
   refresh are idle. First check 15:12:18 UTC: `waiting_for_provider`, 82.6 MB,
   1.185s; next 15:38 UTC. Numerical runtime/activation unchanged.
3. Once available, verify `refresh.json` passed, `data-index.json` through
   September 14, next scheduled producer cycle, relay and actual server delivery.
   No test Telegram messages. See [incident](docs/reviews/2026-09-15-v6-paper-health.md).
4. User asked whether V7 is ready and what should precede build/training. The
   answer is no; follow the ordered [readiness checklist](docs/reviews/2026-09-15-v7-readiness-checkpoint.md).
   Full-universe freeze/build/training remains unlaunched. No subagents authorized.

## V7 acquisition and coding

`healys-v7-download-20260915-budget.service` drained at 07:20:34 UTC with
8,282/8,284 tasks complete, two failures, 52.516 GB charged of 250 GB decimal,
no active tasks/reservations. Root `nn_meta/data_v7/base-20260915r4/`.
All 5,424 stock tasks have receipts (2,712 raw / 2,712 all); 270 observed-empty
responses require PIT/listing/alias investigation. Clarified for user: these
are 135 symbol/year pairs across 62/452 fetch roots (4.98% of captures);
every fetch root has at least one nonempty year. Plain 449-symbol reference:
`docs/specs/v7-tickers-20260915.txt`; detailed empty-year breakdown:
`docs/reviews/2026-09-15-v7-empty-stock-years.md`. Option day/minute each
1,429/1,430; both missing September 14, 2026, direct HEAD still 404.
Retry those missing tasks after publication, preserving receipts and quota.

V7 fixed March 7, 2022–September 14, 2026, 2021 warmup only, full features,
all parameter variants at 1/5/15/30 minutes, actual 1–9 calendar DTE and
observed bid/ask minute execution. Four computation processes /250 GB cap.
Plan `nn_meta/research_plans/v7-20220307-20260914/plan.json`, nested hash
`9a5c1da4c7563471c6bfd73fd30e5eb179c6cb62d497d64c1545f468c7974b09`.

Source commit 11fef57 and checkpoint 85fe15a pushed in prior turn. Implemented:
full planning catalog, quota/captures, shared MA only, calendar Polars bars,
Arrow/Parquet and mmap/Zarr stores, quote unions and bounded capture, component
pilots. Still needed: all other strategy/full feature adapters, full-history
PIT/vintage/coverage audit, complete outcome-independent quote inventory and
captures, quote accounting, frozen purged folds and end-to-end resource gates.
Trade aggregates are not bid/ask data. External Pine comparison remains
explicitly deferred/unverified; do not invent a new external-parity prerequisite.

SPY 2022 raw/all receipt-verified presence pilot passed: 212,907 matching
observations, 251 sessions, 97,710 regular minutes, zero missing. Full universe
not coverage-admitted. Detailed paths and benchmark measurements are in
[download/performance review](docs/reviews/2026-09-15-v7-download-and-performance.md).

## V6 operational paths and dashboard

Home `/home/healy/Coding/HealysV6/nn_meta/live/v6_server`, runtime d6660af,
release `v6-cash-repair-20260913`, 40 GBT members/164 features/449 symbols.
Data root `/home/healy/Coding/HealysBacktester/nn_meta/live/v6_server/data`.
Server `/home/mrhea/HealysV6`; SSH `ssh -o BatchMode=yes mrhea@62.238.20.66`.
Delivery DB `/home/mrhea/HealysBacktester/nn_meta/live/.alert_batches.sqlite3`,
`v6_notices`. Earlier overnight inspection: 25 cycles, four open/two closed,
eight sent/zero pending; no new accepted market cycle established this turn.

Existing forward/data/relay services remain intact. Retry helper is a new
separate main-checkout script and service/timer, not a change to the activated
runtime. Availability polling never publishes inputs or forces a paper pass.
Full tests: **1,651 passed +18 subtests**, 18 warnings, 66.76s, log
`/tmp/healys-v6-context-retry-tests.log`; unit/schedule verification passed.

Dashboard V6 Paper frontend source is prepared in sibling
`/home/healy/Coding/HealyLabsDashboard`, branch `ops/firebase-dashboard-20260911`,
but hosting not deployed. Home env still lacks `V6_FORWARD_ROOT` and
`V6_FORWARD_EVIDENCE`; separate evidence DB not initialized. Existing publishers
working is not evidence of that tab being live. Complete this forward evidence
work alongside V7 preparation. Old short-DTE campaign remains stopped, timer
disabled, 21 completed symbols preserved; do not resume.

## Git and durable state

Commit/push only this turn's helper, tests, units and scoped documentation.
Preserve numerous unrelated prior V6/TradingView/dashboard changes. Never stage
bulk data, validation outputs, credentials or `nn_meta/artifacts_v6/`.
[Prior checkpoint](handoff-history/HANDOFF-2026-09-15-before-context-retry.md)
retains full earlier details. Git staging, user bus, SSH and sibling installs
require appropriate sandbox escalation.
