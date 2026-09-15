# Actual 1–9 DTE dataset/training campaign running now; paper V6 active

Updated September 14, 2026. The user explicitly requested starting now after
compute assessment. **Active campaign: `v6-short-dte-20260914-now`.** The
bounded service started at **20:01:57 UTC / 3:01:57 p.m. Central** and is
running. It verifies inputs, builds all 449 symbols, assembles with PIT
membership, audits, then automatically trains three revalidation folds and
40 final GBT members. Actual model fitting waits for the full dataset/audit.

One worker, two training threads, CPUQuota=200%, MemoryMax=8GiB, no swap,
Nice=15. Today's explicit early-start exception is frozen in a fresh scope;
it retains the 08:30 UTC / 3:30 a.m. Central cutoff before morning refresh.
The service permits up to 24h for this extended first run, with the Python
cutoff enforcing the earlier 08:30 boundary. Future resumes use the original
22:30–08:30 UTC nightly window. Completed symbols/seeds resume. User lingering
is enabled. The previous `v6-short-dte-20260914-launch` dataset and progress
timers are disabled, so the old queued campaign will not run.

Scope SHA256: `170b630e0d91ed0df705bdfbdcc3c26bc446ae2cf197b56bcb9ed37f7f60b59b`.
Only the orchestration script changed from the verified launch snapshot;
model design, all dataset code, raw seal and feature/execution contracts match.
61 focused tests passed, including early-start cutoff/future-day rejection.
Systemd confirmed the service active/running with the intended resource caps.
The new campaign/progress timers are enabled. Paper services are preserved.

Host: Ryzen 7 9850X3D (8 cores/16 threads), 32GB RAM, about 540GB free NVMe,
RTX 3060 Ti 8GB. GBT uses CPU. About 26GiB was available before this launch.

A genuine end-to-end SPY pilot completed successfully: 80 raw rows, 70
executed, 146 filled legs / 76 rolls; membership retained 10 rows and 550 marks.
All 164 features, feature contract, marks coverage, entry/roll cash/DTE audits
and stage receipts passed. All 123,471 sealed raw files were verified. The
original two-signal pilot was excluded by PIT membership, so the pilot now
uses the first 16 frozen MA signals; failed evidence is retained. The successful
pilot ran under a 6GiB cgroup cap, reached that cap including file cache, and
completed without OOM. The pilot and original scheduled scope used identical 304-file snapshots;
only scheduling orchestration changed for the immediate-start scope.
60 focused campaign/training/watcher tests passed this turn.

Paths (relative to this checkout):
- Scope/source/artifacts: `nn_meta/campaigns/v6-short-dte-20260914-now/v6/`.
- Main log/status: that base's `runs/service.log` and `runs/status.json` (written by the active process).
- Progress: `logs/v6-progress/v6-short-dte-20260914-now/progress.txt` and
  `latest.json`; watcher succeeded, Telegram OFF.
- Evidence: `nn_meta/validation/v6-short-dte-launch-20260914/compute.json` and
  `verification.json`; launch review below.
- Units: `healys-v6-short-dte-20260914-now.service/.timer` and the matching
  `-progress.service/.timer`; use `systemctl --user` to inspect them.

The local paper producer, deployed broad-DTE model and Hetzner delivery remain
active. The last scanner result checked during pilot work was successful.
No short-DTE model has been trained or deployed yet. See
`docs/reviews/2026-09-14-v6-short-dte-launch.md` for launch evidence and limits.

## Half-hour updates in the current session

User requested updates here every 30 minutes. Installed and enabled
`healys-v6-session-updates.timer` and its service. `scripts/v6_session_updates.py`
checks a persisted 30-minute deadline once per minute; when due, it submits a
read-only progress prompt to the same Herdr pane/terminal, only while idle/done.
It defers while working/blocked, checks terminal identity/cwd, and the queued
prompt verifies this exact Codex thread before reporting. No separate agent
or Telegram delivery. The shared Codex daemon was unavailable; Herdr is the
active session host. Target verification passed, timer active, service success;
no scheduled prompt has been delivered yet as of setup.

State/cancel flag: `logs/v6-progress/v6-short-dte-20260914-now/session-updates.json`.
Set `stopped` to true to cancel without changing any campaign service. The
prompt instructs the assistant to stop updates after a final completion report
or on user cancellation. Reports include symbols, current stage, training
folds/members when relevant, and failures/pauses. Later chat activity may defer
a due update until this session is idle. Keep Herdr running.

## Current verified deployment

- Home producer: `/home/healy/Coding/HealysV6`, permanent detached checkout.
  Server V6: `/home/mrhea/HealysV6`, branch `ops/v6-forward-20260914`.
  Runtime commit on both: **`d6660af`**. Later documentation-only commits may
  advance checkout HEAD; activation binds runtime bytes, not documentation.
- Existing server production: `/home/mrhea/HealysBacktester`, branch
  `ops/server-alert-readiness-20260906`, commit **`093c117`**.
  Its existing minute dispatcher sends V6's allocated paper notices separately
  from the older four experts' unchanged top-five ranking.
- The final deployment script completed. Activation passed at **16:04:10 UTC**;
  home units were reinstalled at the same time. No deployment script or heavy
  validation run needs resuming. `/tmp/finish-v6-forward-reviewed.py` is a
  completed one-off script; do not rerun its commit/deploy sequence blindly.
- Server acknowledgment evidence retrieved after the final relay: **7 sent,
  0 pending**, covering six entries and one exit. Watcher healthy at 16:03:51.
  Nine allocation cycles completed by the 16:00 pass, with five positions open
  and one closed. These are paper observations, not broker transactions.
- Latest verified pass before the speed update: 16:00 UTC, 219.226 seconds,
  zero errors. The updated runtime completed a scheduled pass starting 2026-09-14T16:45:05.688406+00:00 in 15.92 seconds and recorded completion successfully. Current portfolio: {"closed": 1, "open": 5}.
- No synthetic test message was sent. Real paper notices were sent; the
  operating watcher also reported the opening deadline miss at 13:51:51 UTC.
  The separate completed-training watcher's Telegram setting remains OFF.

## Frozen model and the authorized expiry change

Release: `deploy/v6/releases/v6-cash-repair-20260913/`.
Release SHA256:
`3bc974679fff04044002f833cbb4c9246f63fd4d9370c04985f5f6ca7597764f`.
Model/config SHA256:
`cdacbea1bf6a07e573af46b8d266b1d82b5e3bf736945a06b929e46050fdbd6c`.
40 GBT members, two heads, 164 features, 449 frozen symbols.

The user's exact instruction was: **“Use the explicit 15-minute expiry cutoff
for experimental paper alerts.”** It refers to each option's final regular
session close. Ordinary equity cutoff is 15:45 Eastern (12:45 early close);
eligible late-close ETF/ETN options, including SPY/QQQ, use 16:00 (13:00 early
close). Holiday/weekend expiry uses the last covered exchange session. These
are trigger times; actual receipt/fill times remain separate. Index options
are outside this stock/ETF scope. See `v6_option_sessions.py` and the review.

Weights, entry selection, sizing and underlying strategy exits stay frozen:
EV threshold .05; no DD brake; five slots; one position per symbol; 10% cap;
EV-weighted fractional sizing; 5% underlying stop; take-profit/trailing off;
60-roll cap. The classifier label is excess return, not calibrated profit
probability. Original target grid [1,5,10,30,45], with [2,4,7] on the 15 weekly
names, still competes by EV. There is no enforced actual-short-DTE restriction
on this deployed model and no +200% realized-return cap.

Forward buys use current MASSIVE ask, sales use bid, plus frozen 0.15% modeled
cost per side. Positive two-sided prices/sizes, SIP timestamp after trigger,
and quote age <=30s are required. Entries must complete within five minutes
of signal close. Unfillable selections do not backfill lower-ranked names.
Historical MASSIVE quotes/trades supplied features; option aggregate opens/
closes supplied historical P&L labels. Do not conflate those historical fills
with the separately recorded current paper quotes.

## Operating paths, clocks and data

Home state: `/home/healy/Coding/HealysV6/nn_meta/live/v6_server/`:
`status.json`, `activation.json`, `portfolio.sqlite3`, `data-index.json`,
`market/`, `stock-captures/`, `passes/`, `alert-spool/`, `relay.json`.
Server state: `/home/mrhea/HealysV6/nn_meta/live/v6_server/`:
`incoming/status.json`, `incoming/alert-spool/`, `health.json`.
Server dispatcher DB: production `nn_meta/live/.alert_batches.sqlite3`,
`v6_notices` table records actual delivery status.

Home user timers: `healys-v6-forward` (quarter hours +5 seconds, weekdays),
`healys-v6-relay` (every minute), `healys-v6-data` (09/11/12 UTC, Mon–Sat).
Forward uses 16 workers, single-thread BLAS/OMP/Numba, Nice=5, MemoryMax=18GB.
Calendar gates restrict actual trading sessions. Server `healys-v6-watch.timer`
runs every minute; old `healys-v6-observer.timer` is disabled. The watcher
checks due passes and deliveries and deduplicates failure notices hourly.

Complete immutable data through September 11 lives in the main checkout at
`nn_meta/live/v6_server/data/20260914/`, manifest SHA256
`d94a7e6595a4c634be059131a28d92da7fd976006eb4416a0f7ed8d437511969`.
Full original technical/raw history is preserved; daily refresh publishes an
atomic verified pointer. Twelve adjusted histories required full restatement.
444 frozen symbols had current bars; SATS/SAVA/SWTX/WBA/X remain in the 449-name
inventory with explicit missing-current-bar evidence. Never silently remove
those names or rebase indicator history. Held-symbol data failure blocks new
allocation; expiry handling has a quote-based fallback.

Source runs through Git only; state/data may use rsync. Existing production
feed has a prior subscription deadlock fix absent from main's older feed
file: do not overwrite it with main's `option_stream.py`. V6 uses MASSIVE REST
for complete candidate feature windows; the existing watched OPRA stream is
not evidence of complete V6 receipt coverage. No second competing socket.

## Validation and first-session observations

Evidence root: `nn_meta/validation/v6-forward-20260914/`.
- `feature-parity-reuse/report.json`: three original training cases, all 164
  feature values exact; both prediction heads differ at most floating rounding.
- `replay-friday-cold/status.json`: fresh MASSIVE REST pass, 444 current names,
  888 candidates, zero errors, 261.667 seconds.
- `opening-canonical/status.json`: exact captured opening-query replay,
  921 proposals, **4,722 candidates, zero errors, 275.047 seconds**.
- `opening-parity.json`: all feature values/predictions and the whole candidate
  parquet byte-identical, SHA256
  `34df662507143333fe7d4b3412046e3820c68c21e40a4e27fa2923b60b72efdf`.
  The saved retrospective query has 921 proposals; the first actual live pass
  had 920. Equality compares identical saved inputs, not different API vintages.
- Activation binds **346 passing test executions**: 177 runtime, 59 bridge/
  legacy dispatcher, 110 final focused tests. These include overlapping tests;
  do not call them 346 distinct tests. Additional expiry and on-server bridge
  checks passed. External exported TradingView/Pine parity remains deferred.
- `server-final.json`: seven actual server send acknowledgments and healthy
  watcher. `live-verification.json`: positions and cycles. Compact tracked
  evidence: `docs/reviews/2026-09-14-v6-forward-verification.json`.

Opening 13:45:20 UTC pass took 379.983s and correctly opened no positions.
The 14:00 pass opened FXI, USAR, DUOL and BILI. USAR later closed through its
frozen strategy; ETSY and MDB subsequently opened. No forward return verdict
is drawn from this tiny sample. The exact source reuse update reduces duplicate
indicator calculations, saves actual stock query panels, and skips candidate
work when all five slots remain occupied after causal exit checks. It changes
neither features nor predictions; late future passes still fail closed.

## Actual 1–9 DTE campaign: prepared, not launched

Read `docs/specs/V6_SHORT_DTE_EXPERIMENT.md` and
`docs/reviews/2026-09-13-v6-dte-selection-audit.md` before implementation.
Strict actual-DTE selection, entry/roll audits, separate data construction,
training, independent ledger comparison and overnight units are implemented.
Scope: `nn_meta/campaigns/v6-short-dte-20260914/v6/short_dte_scope.json`;
runner: `scripts/v6_short_dte_campaign.py`; frozen code: the scope's `source/`.
The fresh full dataset and trained model remain outstanding. A shorter target
alone is insufficient; the new policy checks resolved OCC expiry on every
entry/roll and rejects purchases delayed into 0DTE.

The prepared design fixes `[1,5]` plus the existing weekly `[2,4,7]`, preserves
164 features and the dte_frac /45 scale, and uses historical aggregate fills
with unchanged costs. Missing replacements terminate after the prior sale.
It fixes the deployed GBT/Huber, EV .05/no-brake configuration; three historical
folds and forty final members use a distinct research identity. No new family
or threshold search. The unchanged broad-DTE frozen baseline is compared on
the same purged split dates. Reuse only verified compatible raw inputs; never
invoke the broad-DTE continuation/finalizer for this dataset.
145 tests passed. The bounded SPY pilot reconciled eleven legs/six rolls and
new tick materialization. The isolated source loaded the real technical/PIT
context; ten SPY rows matched all 106 expanded feature values exactly, including
missingness and the original DTE scale. All four generated units passed systemd validation. Full raw-cache
verification and full feature/label construction still precede training.
Do not optimize for a promised 1,000% winner. Retain raw return tails and report
train-only winsor bounds. May–August 2026 is already inspected revalidation;
future evaluation dates must be declared before seeing their outcomes.

Original repaired training outputs:
`nn_meta/campaigns/v6-cash-repair-20260913/v6/`.
Original expanded inputs:
`nn_meta/expanded_inputs/v6-local-20260906/full-run/final-inputs.json`.
Original repaired data:
`nn_meta/data_candidates/audit-repair-20260905-final/cache/`.
Previous complete training/server context is archived at
`handoff-history/HANDOFF-2026-09-14-before-forward-activation.md`.

Protect the live producer: it shares this 32GB host and main's venv. The new
units cap training at 8 GiB, one worker/two threads and 200% CPU, scheduled
22:30–08:30 UTC. No live services or dependencies changed. Install the exact
new campaign/progress units when launching; its watcher has Telegram OFF.
The existing completed-training watcher still follows the old campaign.

## Notes, workspace and remaining follow-ups

Main remains dirty with previously authorized training/runtime work. Preserve
all of it, especially preexisting untracked `nn_meta/artifacts_v6/`; do not add
that directory. Editable deployment branches remain in
`/tmp/healys-v6-forward-deploy` and `/tmp/healys-v6-feed-deploy`.
Do not reset main or merge older production source over the research changes.

Dashboard URL: **https://stonks-22367.web.app**. Existing training views are
available; the new forward portfolio has NOT been added to its publisher.
First operational week began September 14 (experimental paper); review on or
after September 21 once the other current TODOs are complete. Durable edge,
full execution/roll history and external Pine parity remain unproven.
