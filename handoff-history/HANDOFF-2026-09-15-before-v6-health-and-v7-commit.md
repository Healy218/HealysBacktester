# V7 acquisition running; performance pilots completed; V6 health check next

Updated September 15, 2026, approximately 00:34 Central. User is clearing context.

## Immediate continuation

1. User asked: “when we find time make sure our v6 paper trading is still going and updating.” **Fresh check is unfinished.** Local `systemctl --user list-timers --all --no-pager` failed with sandbox bus permission denied; rerun with required escalation. Inspect home producer/refresh/relay, ledger freshness, server delivery and dashboard publisher. Overnight idle outside market hours is expected; verify next-session refresh scheduling. Do not send test Telegram messages.
2. Finish documentation and scoped commits/push for the completed V7 acquisition/performance work. Extensive unrelated prior changes exist: preserve them. Do not stage bulk data or `nn_meta/artifacts_v6/`.
3. Continue remaining V7 implementation/readiness gates below while downloads run. Do not restart old short-DTE campaign.

## Authorized V7 scope

Fresh **V7**, March 7, 2022 through September 14, 2026 (fixed last completed session), all registered strategy/parameter variants at 1/5/15/30-minute signals, one-minute observed MASSIVE bid/ask execution, actual 1–9 calendar DTE. Full feature suite, PIT universe/history aliases, new chronological purged walk-forward folds. Older data is warmup only, not fabricated quote labels. User authorized four computation processes and **250 GB decimal disk allocation**. No subagents authorized.

Plan: `nn_meta/research_plans/v7-20220307-20260914/plan.json`; nested plan hash `9a5c1da4c7563471c6bfd73fd30e5eb179c6cb62d497d64c1545f468c7974b09`.
Catalog: 2,817 parameter variants/timeframe, 11,268/ticker, 5,059,332 for 449 tickers before directions/DTE/events. Eight TradingView strategies plus five feature-only scopes; full legacy families included. External Pine parity remains unverified.

## Download RUNNING independently of chat

User systemd unit: **`healys-v7-download-20260915-budget.service`**.
Root: **`nn_meta/data_v7/base-20260915r4/`**; status `status.json`, acquisition `acquisition.json`, frozen launcher `source/download_v7_data.py`.
Quota: `nn_meta/data_v7/quota.json`; global locks `.quota.lock`, `.acquisition.lock`.

Snapshot 2026-09-15T05:33:47.755402+00:00: **1,683/8,284 tasks, 0 failed, running; 10.56 GB used**. Read status again for current progress.

- Four spawned processes, one inner thread; MemoryMax 8 GiB / High 7 GiB, no swap; CPU 300%, Nice 15; 100 GiB free-space reserve.
- 250,000,000,000-byte global cap; 1 GiB per-task reservations, actual bytes charged including partials, hardlinks counted once. Stops new tasks at capacity; fails safe after 20 failures.
- Persistent unit installed at `/home/healy/.config/systemd/user/healys-v7-download-20260915-budget.service` and enabled by absolute file path for reboot recovery. Committed-source candidate: `deploy/v7/healys-v7-download-20260915-budget.service`. Current active fragment is transient; no restart needed. Restart=no avoids capacity retry loops.
- 8,284 acquisition tasks: 452 fetch symbols × 6 years × raw/all stock price bases, plus 1,430 sessions of option day and minute aggregates. Warmup starts 2021-01-01. Full exchange calendar captured through September 14, 2026.
- Alpaca SIP 1Min, all hours retained, `asof="-"` mapping disabled, raw compressed provider pages plus streamed Parquet; complete pagination, OHLC/order validation and hashes. Empty captures need listing/coverage audit.
- MASSIVE all-market option day/minute trade aggregate gz retained and verified. These are **not bid/ask quotes**. Full execution quote inventory is still needed.
- Earlier roots `base-20260915`, `...r2`, `...r3` preserved. r4 reused 299 verified completed tasks by hardlink. Old uncapped unit stopped.
- Do not reset/recover base quota concurrently with quote helper workers; no quote helper remains active at this checkpoint.

## Implemented, tested, still UNCOMMITTED

Detailed review: [V7 download and performance](docs/reviews/2026-09-15-v7-download-and-performance.md).

- `requirements-v7.txt`: numpy 1.26.4, pyarrow 25.0.1, polars 1.44.2, zarr 2.18.7, numcodecs 0.15.1 installed. Existing TF/vectorbt environment preserved.
- `nn_meta/v7/runtime.py`: explicit inner thread limits, spawn pool, Blosc one thread. Arrow already mimalloc; THP already enabled. No allocator/sysctl/mount changes.
- `storage.py`: immutable atomic streamed Parquet/Arrow IPC tables and NumPy mmap/Zarr matrices with hashes, dtype/shape/column metadata, read-only reopening.
- `signals.py`: shared vectorbt MA windows computed once, bounded variant batches. **MA adapter only**; full strategy families not yet implemented.
- `bars.py`: Polars calendar-aware 1/5/15/30 aggregation with observed-minute counts, no gap filling, bucket-close availability.
- `quotes.py`: deterministic bounded request unions by contract/kind/window, preserves request memberships.
- `scripts/download_v7_data.py`: durable bounded download/receipts/quota/recovery.
- `scripts/capture_v7_quotes.py`: up to 10,000 requests per batch, shared quota, complete verified immutable captures, reuse, metadata reservation. Full outcome-independent request generator still missing.
- `scripts/build_v7_working_set.py`: verified stock receipt → four timeframe bars → shared MA/vectorized signal batches → Arrow/Parquet events and NumPy/Zarr arrays. Explicit pilot cap 64 variants; not full feature/option build.
- `scripts/benchmark_v7_storage.py`: real data, consumed numeric warm reads, checksums, four spawned trials and Pandas/Polars parity.
- `tests/test_v7_download.py` (9 tests), `tests/test_v7_performance.py` (12 tests).
- `.gitignore` has new `/nn_meta/data_v7/` and `/nn_meta/research_plans/` lines mixed with older changes; stage only these additions if making a scoped commit.

### Evidence and measured limits

Full suite **1,646 passed + 18 subtests**, 18 dependency warnings, 69.32s: `/tmp/healys-v7-data-performance-tests.log`. Subsequent quote metadata-reservation change verified with actual successful capture reuse. Final shared-column metadata verified by repeated working pilot. No need repeat whole suite unless new code changes.

- Storage: `nn_meta/validation/v7-storage-20260915/report.json`: SPY 2022, 212,907 × 5 OHLCV values. Parquet write/read .0439/.0068s, 2.57 MB; Arrow .0259/.0042s, 8.52 MB; NumPy .0307/.0033s, 8.52 MB; Zarr .0663/.0078s, 4.69 MB. Equal consumed numeric hashes. Arrow about 1.6× warm-read speed at 3.3× space; Zarr slower than mmap in this trial. Selectable backends, no blanket replacement.
- Polars session aggregation 6.6–10.5× faster than measured Pandas reference on this shard. Warm-cache transform benchmark, **not end-to-end speedup**.
- `nn_meta/validation/v7-working-pilot-20260915r2/report.json`: four workers, 64 MA variants/timeframe, Arrow events/Zarr arrays. 1m/5m/15m/30m bars 97,710/19,542/6,514/3,257; events 743,958/137,050/43,880/21,080. Shared MA computed once per timeframe; per-worker peak about 759/526/486/485 MiB.
- Quote pilot `nn_meta/data_v7/quote-access-pilot-20260915/report.json`: SPY220311C00420000, March 7, 2022 14:31–14:36 UTC. Three requests deduplicated to two captures, **1,432 quotes and 2 trades**. Repeat reused verified captures. Access/union test, not contract-selection/fill audit.

### Required before full build/training

Complete acquisition and coverage/listing/alias audit; implement all strategy/timeframe adapters and full feature dependencies; build complete outcome-independent contract/time requests; capture entry/mark/exit/roll quotes; implement/audit quote execution labels and portfolio accounting; freeze purged V7 folds; complete representative full-pipeline correctness/resource pilots. **No V7 freeze/build/training of the full universe has started.** Full timeline includes all features only after coverage gates pass.

Old “flatpack” archives were valid option trade aggregates, retained locally as 500 daily `flatfiles_15m` files; no original minute gz found in inspected old caches. Cannot reconstruct minute data or bid/ask from them. New minute archives are retained in V7.

## V6 paper health check details

Home checkout `/home/healy/Coding/HealysV6`; live root `/home/healy/Coding/HealysV6/nn_meta/live/v6_server`. Server checkout `/home/mrhea/HealysV6`; SSH `ssh -o BatchMode=yes mrhea@62.238.20.66`. Runtime d6660af; broad-DTE release `v6-cash-repair-20260913`, 40 GBT members, 164 features, 449 symbols. No broker orders.

Inspect home `status.json`, unit timers and recent results, `scripts/v6_forward_ops.py`, and readonly `portfolio.sqlite3` counts/latest times (avoid dumping feature payloads). Ledger tables: metadata, cycles(bar,recorded_at,payload), positions(key,symbol,state,payload), events(key,recorded_at,kind,payload), outbox(key,kind,created_at,payload,status). Exported outbox is not proof of delivery.
Server actual delivery DB: `/home/mrhea/HealysBacktester/nn_meta/live/.alert_batches.sqlite3`, table `v6_notices`. Inspect status/time counts only, no secrets. Server bridge still in old production checkout.

**Last actual earlier check**, not current: outside-market-hours status September 14 22:45 UTC; next session September 15; data through September 11; relay sent 8 events; 4 open / 2 closed positions, 25 cycles, 0 rolls. Realized contribution about -3.96% excludes unmarked opens, not total return. Verify scheduled morning input refresh and fresh relay before declaring healthy.

## Dashboard / earlier items 2–3

Source implemented and installed in `/home/healy/Coding/HealyLabsDashboard`, branch `ops/firebase-dashboard-20260911`, with main repo copies in `integrations/dashboard/`. V6 Paper tab and separate evidence journal have 9 frontend tests, build and Chrome desktop/phone checks passed. **Hosting NOT deployed and continuous new evidence collection NOT activated.**
Home publisher needs `V6_FORWARD_ROOT=/home/healy/Coding/HealysV6/nn_meta/live/v6_server` and `V6_FORWARD_EVIDENCE=/home/healy/.local/state/healylabs-dashboard/v6-forward-evidence.sqlite3`. Existing publisher units `healys-dashboard-publisher@home.timer` and server equivalent. Do not mistake installed source for live new tab. Chrome `/usr/bin/google-chrome-stable`; user canceled bundled-browser download.

## Paused old short-DTE campaign

`v6-short-dte-20260914-now`: main service stopped, timer disabled, 21 completed symbols preserved. Old 15-minute campaign superseded by V7. Read-only progress timer remains; session-chat updater stopped. Do not resume it.

## Documentation / git next

Prior V7 scope commits 38e137b and **c78722e** were pushed to main. This session's files listed above remain uncommitted. Detailed review and this handoff are saved. Archive: `handoff-history/HANDOFF-2026-09-15-before-v7-download-and-performance.md`.
TODO continuation added at end. Still update ROADMAP/spec/DECISIONS with current implementation and measured limitations, stage only intended files (many preexisting V6/TradingView changes), commit and push. Never stage raw data, validation outputs, credentials or `nn_meta/artifacts_v6/`. Respect required sandbox escalation for .git, user systemd bus, sibling installs and SSH. No background agent or tool session is needed to sustain the running systemd download.
