# V6 overnight health verified; V7 acquisition committed and running

Updated 2026-09-15T05:47:21.689661+00:00.

## Immediate continuation

1. V6 overnight check completed. Observe the scheduled September 15 09:00 UTC
   (04:00 Central) input refresh through September 14, then the regular-session
   producer. No morning run was forced. Full details: [health review](docs/reviews/2026-09-15-v6-paper-health.md).
2. Continue V7 readiness: full-history PIT/listing/alias and feature dependency
   coverage audit, all non-MA strategy/timeframe adapters, complete
   outcome-independent quote request inventory, quote execution/accounting,
   frozen purged folds and representative full-pipeline resource pilots.
   Full-universe build/training remains gated. Do not restart the old short-DTE campaign.
   Known failed acquisition: `options/day_aggs/2026-09-14`, MASSIVE
   `NoSuchKey`. Provider object availability must be rechecked/retried after
   the current four-worker acquisition drains; do not silently drop the fixed
   final session or relabel aggregate coverage complete.
3. Dashboard V6 Paper hosting, publisher inputs and separate continuous evidence
   journal remain to be deployed/configured. Existing publisher success does
   not prove the new tab is live. Prior dashboard work is documented below.

## Authorized scope and running download

V7: March 7, 2022–September 14, 2026 inclusive, fixed completed-session cutoff;
2021 warmup only. Full feature suite, all registered variants at 1/5/15/30
minutes, one-minute observed MASSIVE bid/ask execution, actual 1–9 calendar
DTE. Four computation processes, 250 GB decimal download allocation. No
subagents authorized. External Pine parity remains unverified.

Plan: `nn_meta/research_plans/v7-20220307-20260914/plan.json`;
nested hash `9a5c1da4c7563471c6bfd73fd30e5eb179c6cb62d497d64c1545f468c7974b09`.
Catalog: 2,817 variants/timeframe, 11,268/ticker, 5,059,332 across 449 tickers,
before directions/DTE/events. This is a planning catalog, not a full adapter.

Active user service: `healys-v7-download-20260915-budget.service`.
Root: `nn_meta/data_v7/base-20260915r4/`; source frozen under `source/`.
At 2026-09-15T05:47:21.317543+00:00: **2500/8284 tasks,
1 failures, running; 15.98 GB charged**.
Read fresh status on continuation. This service runs independently of chat.

- Four spawned processes/one inner thread, MemoryMax 8 GiB/High 7 GiB,
  no swap, CPU 300%, Nice 15, 100 GiB free-space reserve.
- Shared `nn_meta/data_v7/quota.json`, `.quota.lock`, `.acquisition.lock`.
  250,000,000,000-byte cap, 1 GiB task reservations, actual retained bytes
  charged including partials; hardlinks counted once. Capacity pauses new
  tasks, 20 failures stops the controller. Do not reconcile/reset quota
  concurrently with quote workers. No quote helper is active.
- Persistent service installed/enabled at
  `/home/healy/.config/systemd/user/healys-v7-download-20260915-budget.service`;
  current running fragment is transient. Restart=no avoids retry loops;
  no restart was made this session.
- 8,284 tasks: 452 literal stock roots × 6 years × raw/all, plus 1,430 option
  day/minute aggregate captures. Alpaca SIP 1Min pages retain all hours and
  `asof=-`; observed-empty captures require listing audit. MASSIVE aggregate
  gzip files are trade OHLCV, not bid/ask. Full quote inventory is outstanding.
- Earlier roots and uncapped attempts preserved; r4 reused 299 verified tasks
  by hardlink. Never alter the frozen running source or relabel old artifacts.

## Implemented and committed

Source commit **11fef57**: bounded base acquisition/quota, quote union/capture,
shared MA indicator batches, calendar-aware Polars bars, immutable
Arrow/Parquet and NumPy mmap/Zarr stores, benchmark/working-pilot scripts,
V7 optional requirements, persistent service and tests. Documentation follows
in a separate commit. Work is on main; unrelated prior changes remain unstaged.

Detailed [download/performance review](docs/reviews/2026-09-15-v7-download-and-performance.md)
holds file map, measurements and limits. Previous full suite:
**1,646 passed + 18 subtests**, 18 dependency warnings, 69.32 seconds,
`/tmp/healys-v7-data-performance-tests.log`. Final capture/metadata changes
also passed real reuse and working-set pilots before handoff. This session
changed documentation only and did not rerun the unchanged full suite.

Evidence under `nn_meta/validation/`:
- `v7-storage-20260915/report.json`: SPY 2022, 212,907 rows × five OHLCV
  columns. Arrow warm read ~1.6x faster than Parquet at 3.3x space; NumPy
  mmap fastest, Zarr slower in this trial. No blanket backend replacement.
- `v7-working-pilot-20260915r2/report.json`: four processes, only 64 MA
  variants/timeframe. Shared MA computed once; bounded events; peak workers
  about 759/526/486/485 MiB. Not the full feature/option pipeline.
- NEW `v7-coverage-pilot-20260915/report.json`: both SPY 2022 raw/all receipts
  and all referenced files hash-verified. Identical 212,907 timestamps;
  251 sessions/97,710 expected regular minutes, zero missing. Presence only,
  not a corporate-action vintage or full-universe PIT audit.
- Quote access/reuse: `nn_meta/data_v7/quote-access-pilot-20260915/report.json`,
  SPY220311C00420000 March 7, 2022 14:31–14:36 UTC; three requests → two
  captures, 1,432 quotes and two trades. Access/union only, not fill audit.

## V6 operating state and remaining acceptance

Home checkout `/home/healy/Coding/HealysV6`, root
`nn_meta/live/v6_server`. Runtime d6660af, release
`v6-cash-repair-20260913`, 40 GBT members, 164 features, 449 symbols.
Server checkout `/home/mrhea/HealysV6`; SSH
`ssh -o BatchMode=yes mrhea@62.238.20.66`. Delivery bridge remains in the
old production checkout; no broker orders.

At September 15 05:38–05:39 UTC: 25 ledger cycles, closing bar 19:45 UTC
recorded 20:03:50 September 14, four open/two closed positions. All eight
notices independently confirmed sent in server DB
`/home/mrhea/HealysBacktester/nn_meta/live/.alert_batches.sqlite3`,
`v6_notices`; none pending. Home relay and server watcher are fresh.
Overnight producer status is expected idle, next session September 15.

Input pointer is still through September 11. No new `refresh.json` exists;
09/11/12 UTC refresh schedule is installed. Verify morning success before
claiming next-session input readiness. Producer timer runs weekdays at
bar-close +5 seconds, 12:00–22:45 UTC; calendar gates market operation.
No test Telegram messages were sent and no runtime source was changed.

Dashboard source: `/home/healy/Coding/HealyLabsDashboard`, branch
`ops/firebase-dashboard-20260911`; copies under main `integrations/dashboard/`.
Prior frontend tests/build and Chrome checks passed, but new hosting is not
deployed. Existing home/server publishers succeeded during this inspection.
Home environment is missing `V6_FORWARD_ROOT` and `V6_FORWARD_EVIDENCE`;
`/home/healy/.local/state/healylabs-dashboard/v6-forward-evidence.sqlite3`
does not exist. Set the root to the permanent HealysV6 state and configure
that separate evidence database, then deploy/verify the frontend within
existing authorization. Do not confuse installed source with live UI.

Paused `v6-short-dte-20260914-now`: stopped, main timer disabled, 21 completed
symbols preserved; read-only progress timer remains. Do not resume it.

## Git and documentation

Scoped V7 source and checkpoint documentation commits only. Preserve all
preexisting V6/TradingView code, docs, artifacts and dashboard changes.
Never stage raw data, validation outputs, credentials or `nn_meta/artifacts_v6/`.
The current handoff is archived at
[previous checkpoint](handoff-history/HANDOFF-2026-09-15-before-v6-health-and-v7-commit.md),
which retains the complete acquisition/performance handoff. Required sandbox
escalation applies to Git staging, user systemd bus, SSH and sibling installs.
