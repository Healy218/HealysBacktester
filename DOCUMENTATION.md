# DOCUMENTATION — coding notes, conventions, traps, ops

Reconciled September 5, 2026. Goals live in [ROADMAP](ROADMAP.md), active tasks
in [TODO](TODO.md), and session milestones in [HANDOFF](HANDOFF.md).
The previous technical reference is preserved in
[handoff-history](handoff-history/DOCUMENTATION-2026-09-05-before-checklist-reconciliation.md).

The active working line is `main` in `/home/healy/Coding/HealysBacktester`
under the user's instruction. Use the project Python 3.12 virtualenv explicitly.
The suite exercises LightGBM/TensorFlow on synthetic fixtures without network
or production artifacts. The September 6 raw-price/live-data continuation
passed 1,143 tests and 18 subtests (11 warnings); the September 5 integration
baseline was 642 tests and 18 subtests. The final expanded v6 integration
passed 1,390 tests and 18 subtests (11 warnings, 45.43 seconds).

The September 5 audit began with feature/build contract `2026-09-05-causal-v2`;
the raw-price continuation advances it to `2026-09-06-raw-spot-v3`.
Expanded v6 has a distinct opt-in contract, `2026-09-06-tv13-option-ticks-v4`,
with twenty families and 106 additional features.
[Expanded input/launch runbook](docs/specs/V6_EXPANDED_INPUTS.md).
Pre-audit freezes, partial checkpoints, rows, marks and bundles must be rebuilt
and validated under that contract; preserve existing files as historical
artifacts, and do not relabel them to bypass verification. Historical returns
and gate verdicts below are not corrected performance evidence. Evaluation
with a globally frozen proposal generator is restricted to periods after its
optimization horizon; it is conditional on that generator, not end-to-end
fold-local refreezing.

Current default bundle verification covers the feature contract and all
load-critical artifacts. Older claims that unverifiable bundles are usable
refer to previous code, not deployment eligibility with this version.

Massive Advanced supersedes the former two-year entitlement cap; existing
label windows are frozen research choices. Production cadence is :01/:02/:03
by pool (verified on the server 2026-09-08). For process health checks use an
ANCHORED pattern (`pgrep -f 'feeds\.stock_stream$'`); the bracket trick alone
does not protect a line that also spells out the module path (Traps).

Live readers retain streamed current-session bars and forced REST fallback,
with actual closed-bar freshness checks. Future delta-targeted contract
selection/intraday features require matching offline selection/features and
versioned provenance. Quote-verified NBBO accounting is planned work, not a
claim made by the corrected OHLCV ledger. See
[REALTIME_SPEC](docs/specs/REALTIME_SPEC.md) for the preserved v7 contract.

See [audit remediation](docs/reviews/2026-09-05-remediation.md) and the
[original audit](docs/reviews/2026-09-05-adversarial-audit.md) for implemented
repairs and migration requirements.

## V7 completion workflow and evidence index (September 17)

[TODO](TODO.md) now starts with report items **6-1 through 6-7**. Work on one
current deliverable, named in [HANDOFF](HANDOFF.md), until its stated scope and
completion evidence are satisfied. Update the checklist and evidence, archive
HANDOFF, write the next numbered handoff, then commit and push. An incomplete
item stays current. The report's pause and older parallel-work instructions do
not override this user-selected sequence.

The [three-day report](docs/reviews/2026-09-17-three-day-goals-and-progress.md)
is the evidence index for work completed September 15–17, with detailed review
links. Its sections 3A–3B are the starting point for **6-1 identity/actions**;
sections 3C–3H map the later consumers and gates. [ROADMAP](ROADMAP.md) preserves
the completed-work summary and deferred backlog. The
[old TODO](handoff-history/TODO-2026-09-17-before-report-sequence.md) is historical,
not a second active queue. Do not reconstruct all prior work on every session.

Keep these evidence distinctions explicit: session presence is not every-minute
coverage; provider records are not distinct actions; an inventory is not admitted
causal history; retrospective explanation is not contemporaneous observability;
component tests and a real AAPL pilot are not full-universe readiness. Reuse the
captured inputs and implement scalable consumption. Additional acquisition must
serve an identified missing input for the current deliverable. No blanket
requirement to collect issuer publications for every record is introduced by
this workflow, and no existing causal requirement is waived.

## V6 forward paper operating contract (September 14)

The active frozen producer is `scripts/run_v6_forward.py` in the permanent
`/home/healy/Coding/HealysV6` checkout. Main is the research workspace, not the
running source checkout. Its `nn_meta/live/v6_server/portfolio.sqlite3` owns
positions/cycles/outbox; the server's separate V6 checkout receives generated
state and the existing production dispatcher delivers immutable notices.
Existing four-expert ranking and feed fixes are preserved. Source deployment
uses Git; generated data/state may use rsync. Exact paths and receipts are in
[HANDOFF](HANDOFF.md) and the
[activation review](docs/reviews/2026-09-14-v6-forward-activation.md).

- Preserve the full original adjusted/raw history and price vintage. Rebase or
  missing held-symbol data must not silently alter strategy exits/features.
- Apply expiry cutoff to the option class's final regular session; stock close
  differs from eligible ETF option close. Use the covered calendar for holidays
  and early closes. Actual quote receipt/fill is later than the trigger.
- Real MASSIVE tick features use their original SIP/condition/missingness rules.
  Current arithmetic bid/ask midpoint paper fills keep actual receipt times. Historical aggregate
  labels and paper quote fills are different evidence; neither is a broker fill.
- Activation binds source/evidence hashes. Editing installed numerical source
  breaks activation; never mutate it during a pass. New source needs reviewed
  parity evidence and activation. Documentation-only changes do not affect it.
- `v3/_source_memo.py` reuses identical numerical inputs only within one V6
  symbol. Pandas storage layout is not numerical identity; keys include actual
  values/index/attributes. Cached outputs are detached. Changing numerical
  sources while a replay runs triggers the source guard.
- The producer shares a 32GB host and main's venv with research. Its 18GB cap
  and the prior training 24GB cap do not form a viable simultaneous budget.
  Measure combined resources, isolate new source/artifacts and protect scheduled
  market scans before starting short-DTE training. Do not update the shared
  environment while the producer operates.
- Superseded short-DTE campaign: `v6-short-dte-20260914-now` is stopped,
  with its main timer disabled and 21 completed symbols preserved. V7 replaces
  this research scope; do not resume the old build. Its read-only progress
  timer was also disabled/stopped September 17. Historical [launch review](docs/reviews/2026-09-14-v6-short-dte-launch.md).
- Paper health watcher and completed-training watcher are independent. Bind a
  new training watcher to the exact new campaign/service; never assume the old
  completed-run binding follows a new run automatically.
- The legacy observer/snapshot-shadow route remains available for research but
  its waiting timer is disabled. Reinstalling it is not an activation step.

## V7 acquisition operating contract (September 15)

Base acquisition and quote captures share the decimal 250 GB ledger under
`nn_meta/data_v7/`. Do not reset/reconcile that ledger while quote workers
are active. Preserve partial attempts and original receipts; a capacity pause
is not completion. Run only one base controller. The active frozen launcher,
unit and checkpoint paths are recorded in HANDOFF; editing research source
must not mutate its frozen copy. Full build/training stays behind the V7
readiness gates. [Run details](docs/reviews/2026-09-15-v7-download-and-performance.md).

## Environment

- **Repo**: `/home/healy/Coding/HealysBacktester`, working branch `main`.
  A local merge does not update the deployed checkout.
- **Python**: `./venv/bin/python` (3.12.14). Always call the venv explicitly.
- **Tests**: `./venv/bin/python -m pytest tests/ -q`; 1,143 tests and 18 subtests
  at the September 6 continuation milestone. Tests exercise installed
  LightGBM/TF using synthetic data, without network or production artifacts.
  Install pytest separately from runtime requirements when preparing a venv.
- **Secrets**: `.env` at repo root, never in git. Keys: `ALPACA_API_*`,
  `MASSIVE_API_KEY`, `MASSIVE_FLAT_FILES_API_*`, `ALPHAVANTAGE_KEY`,
  `FINNHUB_API_KEY`, `REDDIT_CLIENT_*`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `FA_SKIP_COLLECTORS`.
- **`NN_META_POOL`** selects the strategy pool AND suffixes every artifact
  dir (`nn_meta/config.py`): v2 (default) / v3 (live scanner) / v31 (at-scale
  + v4 work) / v5 / v6 / spx0. v5 and v6 share `data_cache_v5` but have
  separate artifact outputs; v6 keeps v5's window. Wrong pool settings can
  silently read/write the wrong directories.
- **Home box** (rebuilt 2026-08-23): Ryzen 7 9850X3D (8C/16T + iGPU),
  32 GB DDR5, RTX 3060 Ti, 1 TB NVMe, CachyOS, user `healy`. The old
  i5-11400/B560 build (proven RAM fault — hourly `fa.collect` segfaults on
  its final morning) is retired; the drive moved over intact, so the OS
  install and all paths are unchanged. TF is CPU-only here in practice; the
  heavy work is memory-bound dataset building. The September 3 user decision
  runs assembly/training on this box; cloud is optional measured acceleration.
  The old faulty-RAM training restriction applied to the retired hardware.

## Conventions

- Small, single-purpose, specifically-messaged commits. Commit and push
  often — don't leave hours of work sitting uncommitted.
- **Scripts derive their own repo root**:
  `cd "$(dirname "$(readlink -f "$0")")/.."`. Never reintroduce an absolute
  local path — that's what broke every launcher when the WSL2 box was retired.
- **Never hardcode worker/shard counts.** Source `scripts/lib/autosize.sh`
  and call `autosize_workers <per_worker_mb>`; it divides MemAvailable (less
  a 2 GB reserve) by the budget and caps at `nproc`. Measure per-worker RSS
  for the current stage/pool; old freeze/build measurements are not fixed
  worker-count prescriptions for later campaigns.
- **All long-lived parquet writes are atomic** (tmp + rename). A truncated
  parquet once crash-looped two build shards for 3+ hours; leftover `*.tmp`
  files after a kill are harmless litter.
- **Long jobs register with the reboot-recovery dispatcher**
  (`scripts/boot_restart.sh`, descriptors in `scripts/jobs.d/` — see its
  README): create an **empty** marker in `scripts/.jobstate/` at launch,
  write the exit code on completion. Absent marker = never started here =
  dispatcher leaves it alone. The systemd unit
  (`deploy/systemd/healys-boot-restart.service`) is committed but **not
  installed** on the home box — install steps in `deploy/systemd/README.md`
  if unattended recovery is wanted for a long run.
- Log locations are launcher-specific: newer launchers use `logs/`, while
  older jobs write root `*.log`. Inspect the descriptor/launcher when
  wiring a watcher; do not infer the path from an older handoff.
- **v4 policy grid = filter × rank × `ev`** (2026-08-21). Every v4
  predictor carries two heads: P(win) (`predict`) and a magnitude head
  (`predict_ev`, expected signed net return, Huber on a target winsorized
  at the train 1%/99% — the raw column has a 1526× outlier). `choose_policy`
  adds the `ev` candidates only when `ev_predictions=` is passed, so legacy
  callers stay bit-identical; `config.EV_THRESHOLDS` are in return units.
  The gate is the same for all three modes. The ledger
  (`mark_to_market_portfolio`) takes an optional per-trade `size_fraction`
  in `(0, PORTFOLIO_FRACTION]` — EV sizing may only de-risk, never
  concentrate; `execution_frames` passes it through.
- **Bundle layout** (`model_final_v4/<run_id>/`): `model.keras|joblib` +
  `magnitude.keras|joblib` (+ `scaler.json` for nn) + `params.json`;
  `ensemble_config.json` records `mode` (`filter`/`rank`/`ev`),
  `threshold`, `magnitude_head`. `V4Bundle.decision_score` is what live
  code must threshold on (EV for an `ev` bundle, P(win) otherwise); a bundle
  persisted in `ev` mode fails to load if any member lacks its head. Default
  loaders also require the current feature contract and full verification
  envelope; old bundles are historical and must be rebuilt/retrained.

## Traps — things that look wrong and are not

- **Watchers bind to IDs captured at submit time — never list-and-pick.**
  Two live incidents 2026-08-25: a job watcher re-derived "the newest job"
  from `gcloud batch jobs list` and confidently reported a stale job's
  SUCCEEDED; a `pgrep -f`-based watcher matched its own command line and
  never fired. Rules: (1) `deploy/gcp/submit.sh` writes the submitted job
  name to `deploy/gcp/.last_job` — watch with `deploy/gcp/watch_job.sh`,
  which takes the explicit name; (2) any pgrep-in-a-watcher needs the
  bracket trick (`pgrep -f 'v3\.[f]latfiles'`) so it can't match itself;
  (3) a watcher's terminal print must include EVIDENCE (task events,
  artifact listing), not just the state word.

- **Use arrays or explicit flags, and check the actual shell.** The current
  session uses bash; a previous tool used zsh, where an unquoted flag string
  did not word-split. This produced two false `UNREACHABLE` readings in a
  Batch watcher on 2026-08-20:

      P="--project=healys-batch --location=us-central1"
      gcloud batch jobs describe "$J" $P ...
      # ERROR: The project property must be set to a valid project ID, not the
      #        project name [healys-batch --location=us-central1]

  Inline the flags, or use an array. Note the same call worked fine when typed
  directly, so it reads as a flaky API rather than a quoting bug — check for a
  variable-expanded flag string before blaming the service. (`gcloud storage`
  kept working throughout, because it had no variable to split.)
- **The bracket trick does not protect a line that also contains the
  unbracketed text.** The feed watchdog crons were
  `pgrep -f "[f]eeds.x" || (nohup python -m nn_meta.live.feeds.x &)` — the
  restart half of the same `sh -c` line contains `feeds.x`, so pgrep always
  found the watchdog itself and never restarted a dead daemon (found
  2026-09-08 when a killed option stream stayed down through a cycle). Anchor
  on the daemon's exact command-line end instead: `pgrep -f "feeds\.x$"`.
  Rule (2) above still holds for watchers whose line does not repeat the
  target's name.
- **A missing 1-minute bar is usually a quiet minute, not a stream gap.**
  Alpaca emits a 1m bar only when the symbol traded; even GS misses minutes.
  `barstore.aggregate_15m` used to demand all 15 minutes and threw ~190
  names per cycle onto REST for the rest of the day. It now accepts a gap when
  SPY/QQQ streamed that minute (the stream was provably alive) and still
  rejects — REST fallback — when the reference symbols missed it too.
  `reference=None` restores the strict rule for offline callers.
- **The first pass after a long weekend fires before today's first bar has
  closed.** At 09:31 ET on 2026-09-08 (post Labor Day) the newest closed bar
  was Friday 15:45 ET; a wall-clock "> 30 min old" rule marked all 441 v5
  names stale and burned a pass. `scanner.require_recent_bars` now compares
  against `expected_last_closed_bar` from the captured session calendar
  (`nn_meta/live/exchange_calendar.json` on the server; without one the
  Mon–Fri rule applies, which does not know holidays). "Stale" = more than one
  closed interval behind that bar.
- **Never call alpaca-py's `subscribe_*`/`unsubscribe_*` from inside the
  stream's own event loop once it is running.** They do
  `run_coroutine_threadsafe(..., self._loop).result()` — fine from another
  thread, a deadlock from the loop thread, and the frozen loop cannot even
  write its heartbeat (process alive, 0 CPU, pgrep happy). That froze the
  option stream 30 s after its first contracts arrived on 2026-09-09.
  `option_stream.sync_subscriptions` now registers handlers and awaits
  `_send_subscribe_msg` / `_send_unsubscribe_msg` itself, and a stall-guard
  thread exits the process after 120 s of loop silence so the cron watchdog
  restarts it. Same rule applies to the stock stream if it ever resubscribes
  at runtime.
- **logrotate refuses a group-writable config** ("Ignoring … because of bad
  file mode") and the server's umask checks files out as 664 — that is why
  `scripts/rotate_logs.sh` chmods the conf before every run. Do not "fix"
  the chmod away.
- **Historical shell/tool trap:** a prior privileged-command interface ran
  only the first step of a chained request. Inspect each exit status and use
  the current permission interface for required privileged work. Shell syntax
  follows the actual executor, not the user's interactive fish configuration.
- `BASE=/home/mrhea/HealysBacktester/...` and `SERVER=mrhea@62.238.20.66`
  in `scripts/` are **remote** paths on the Hetzner box, where the user
  really is `mrhea`. Correct as written.
- `scripts/jobs.d/*.sh` are **sourced**, not executed — their missing
  executable bit is correct.
- `scripts/.jobstate/` and root run logs are gitignored, so on a fresh
  checkout every job looks "not done". That's why the absent-marker guard
  exists.
- `requirements.lock.txt` was frozen on a Mac (162 `pyobjc-*` pins) and is
  **unusable on Linux**. To reproduce the v3.1/v4 environment, install
  `requirements.txt` with the D:-backup's `wsl_pip_freeze.txt` as a pip
  constraints file (`-c`).
- **Historical bundles are not eligible inputs.** The July Option A bundle
  predates hashed persistence, and pre-audit bundles lack the current contract.
  Default verification failures are rebuild/refinalize requirements, not
  permission to bypass the loader.
- After any tar-layered restore: `chmod +x scripts/*.sh` — the 07-25 restore
  dropped exec bits and the hourly collector failed `203/EXEC` for a day.
- **Comparing two dataset builds: use `nn_meta.dataset_diff`, never a naive
  sort-and-walk.** Both frames carry duplicate keys, so pairing by sorted order
  mis-pairs rows and every mis-pair reads as a difference — that path invented
  845 fake `dte` diffs on AAPL (2026-08-19). And the obvious keys are the wrong
  keys: `contract`/`strike`/`expiration` are exactly what a cache change moves,
  so keying on them hides the thing you are measuring. Align on the SIGNAL:
  `symbol, strategy, entry_ts, direction, right, dte, trade_idx`. `dte` is the
  target bucket (1/5/10/30/45), not days-to-expiry. Omit `dte`+`trade_idx` and
  you match ZERO rows.
- **AAPL is a useless pilot symbol for cache work**, despite being the README's
  canonical pilot (`submit.sh 1 "AAPL,SPY"`). It was built 08-17 against a
  complete cache, so it rebuilds byte-identical no matter what — a pilot on it
  alone reads as "the cache theory is refuted", which is wrong. Pick a symbol
  confirmed affected first.
- **The 9y 1m crawl is missing 31 Dec of every completed year, except for SPY
  and QQQ.** `v3/underlying.py` asked Alpaca for `end = "{year}-12-31"`, which
  is midnight, so the final session fell outside every past-year partition.
  Fixed 2026-08-19 for new crawls; the 287 already-stored symbols still have
  the hole, and `underlying_15m`/`underlying_daily` derive from them. This is
  probably part of why `cache_preflight` reports "5 extra" day-frames — a day
  the option archive has and `underlying_15m` lacks reads as extra, not
  missing.
- **Historical crawls and current-session feeds have separate time bounds.**
  The former free Alpaca tier withheld recent SIP data; that entitlement
  restriction ended with Algo Trader Plus on September 5. Historical cache
  requests may still stop at today-00:00 deliberately. Live readers fetch
  today through now without day-keyed cache reads/writes and reject forming
  bars. Do not alter one path on assumptions about the other.
- **`fa/collectors/reddit.py` returns None on 401/403 instead of raising** —
  deliberate. `collect()` decides: it raises only if EVERY listing failed, so a
  credentials outage surfaces as a failure while a single blip does not. Silent
  `+0 rows` is the failure mode being avoided; `fa.collect` counts a collector
  as failed only when it raises.

- **Batch `SCHEDULED` for >10 min with `CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED`
  in `status.statusEvents`** is GCE capacity for that machine family in the
  region, NOT our quota and NOT a job bug (2026-08-21, `n2-standard-8`).
  Batch keeps retrying zones indefinitely. Delete and resubmit with
  `MACHINE=n2d-standard-8` (separate pool) — it provisioned immediately.
- **Two `submit.sh` calls in the same second collide**: the job name is
  `<prefix>-<sha>-<HHMMSS>`, so the second submit errors "already exists" and
  only one job runs. Submit sequentially with a pause, and always LIST the
  jobs afterwards rather than trusting the submit echoes (2026-08-21: two
  evaluate submits produced one job).

## Indicator and campaign contracts

[TRADINGVIEW_EXPANSION](docs/specs/TRADINGVIEW_EXPANSION.md) records the
September 5 listing snapshot and thirteen selected indicators. Boosts define
the requested research scope, not a performance claim. Preserve original
authors, publication versions, source hashes and licenses. An indicator's
calculation and a proposed trade rule are separate interfaces; chart-only
zones/statistics require explicit mechanical rules before proposal admission.

Align numerical outputs and all four signal frames with Pine fixtures and
frozen-parameter replay. A pivot drawn on an earlier bar becomes available at
confirmation; higher-timeframe values and resolved outcome statistics need
their true knowledge times. Geometric OHLCV volume estimates are not native
footprint data. Each admitted intraday feature needs a historical/live twin
and the parity gate in [REALTIME_SPEC](docs/specs/REALTIME_SPEC.md).

For corrected campaigns, preserve old files and allocate fresh paths before
launching. Freeze specs carry the contract/config hash; checkpoints bind
entry, window, DTE grid, execution and costs. Publish marks and rows together,
with provenance last. Assembly checks coverage and the exact frozen source
fingerprint; v5/v6 default to PIT membership. A partial filename alone does
not establish completion. Default spec/model loaders fail on stale inputs.

v6 currently shares v5's window and data cache, with separate output paths.
The September 5 archive audit found fifteen symbols with regular multiple
weekly listings; the implemented extra DTE targets are `[2, 4, 7]`. These are
target-day buckets resolved to available listings, not an implemented
first/second/third-expiration ordinal API. Any deeper window or altered
selection semantics need new generation/provenance inputs.

## Artifact map — historical locations to inventory before migration

This map preserves earlier storage conventions. Check actual contents and
contract compatibility before reuse; the presence of an old file in git or
backup is not current-model eligibility.

| Thing | Where | In git? |
|---|---|---|
| v3 live models + spec | `nn_meta/model_final_v3/`, `artifacts_v3/baseline_spec.json` | yes (force-added) |
| v31 dataset + spec (v4's input) | `nn_meta/artifacts_v31/{meta_dataset.parquet,baseline_spec.json}` | yes |
| v4 Option A bundle | `nn_meta/model_final_v4/` | **no** (gitignored; also in D: backup) |
| v31/v4 reports + manifests | `nn_meta/reports_v31/` | **no** (gitignored; headline tables preserved in `docs/specs/V4_OUTLINE.md` + `docs/v31_run_history.md`) |
| Raw option-bar cache (v31) | `nn_meta/data_cache_v3/` (3.4 GB) | no |
| 9y 1m underlying crawl | `v3/data/` (5.4 GB) | no (tarred on D:) |
| Universe list | `v3/artifacts/universe_120.json` | yes (load-bearing — `config.py` guards on it) |
| FA raw archive | server `fa/archive/` (+ home StockTwits push) | no — append-only, irreplaceable |
| Full restore kit | home box **D: drive (label MRHA)**, three layered folders + `RESTORE.md` | — |

## GCP billing — how it actually works, and how we blew $263 of $300

Written 2026-09-02, the day the v5 campaign ran the free-trial credits down
to $36.85. Read this BEFORE launching any fleet.

### The mechanics that bite

- **A GCP "budget" does NOT cap spending.** It sends email at thresholds.
  There is no native hard spend limit. Believing otherwise is the single
  most dangerous misconception here — see `scripts/cloud_budget_guard.sh`,
  a best-effort time-based cancellation monitor. API failures/unknown states
  require retries and terminal-state evidence; this is not a guaranteed cap.
- **The billing console lags 1–2 days.** Any number you read is the past.
  Never anchor a go/no-go decision on it without adding the burn since.
- **Credit balance is not exposed to gcloud or any API.** Console →
  Billing → Credits is the only source, and it lags. So the ONLY real-time
  spend signal is one you compute yourself from VM-hours.
- **Trial vs PAID matters enormously.** On a trial, compute simply stops
  when credits run out. This account was upgraded 2026-08-27 (to escape the
  32-CPU cap), so now **credits running out means the card gets charged,
  silently**. Upgrading removed the safety net along with the cap.
- **Quota was our accidental cost control.** `CPUS_ALL_REGIONS=32` capped
  us at 4 VMs, which capped burn near $0.70–1.00/h. The quota increase we
  chased all week would have TRIPLED the burn rate. Be careful what you
  wish for: on a paid account, a quota bump is a spend multiplier.
- Local SSD is billed per VM-hour whether or not it is used, and spot
  prices float. Estimate with the WORST-case rate, never the average.

### The post-mortem: a 3–5x estimating miss, not a spending accident

Roughly $15–25 went to genuine mistakes (an I/O-starved fleet that built
one symbol in 11h, a fleet launched against a nonexistent image, two dead
pilots, preemption rework). **That was the small part.** The campaign was
simply more expensive than anyone computed, and nobody computed it:

1. **Burn rate and duration were never multiplied.** ETAs were quoted in
   days ("Thursday, maybe Friday") and costs in dollars ("$20–45"), in
   separate breaths. $16–19/day x 5–7 days = $80–130 for the build stage
   alone. That multiplication was never once performed before launch.
2. **Estimates came from PILOT economics, not FLEET economics.** A solo
   pilot symbol cost ~$0.50 of VM time. But the fleet packs 5 tasks per VM
   and each v5 symbol is ~8h, so the real unit is
   `441 symbols x 8h / 5 per VM = ~706 VM-hours` -> **$105–175 for the
   build stage**, plus ~300 VM-hours (~$45–75) for the freeze. The honest
   pre-launch number was **$150–250 against $162 remaining**. It never fit,
   and five minutes of arithmetic would have said so.
3. **A stale console reading was treated as current.** "$162 remaining"
   (read 08-28) was quoted for days while $16–19/day kept burning.
4. **Every relaunch reset progress-per-dollar.** Four fleet configurations
   in three days each re-staged caches and re-ran in-flight symbols. The
   configs were necessary; the failure was not re-forecasting after each.

### Rules going forward

- **Before any fleet: compute total VM-hours and dollars, in writing.**
  `units x hours-per-unit / tasks-per-VM = VM-hours`, x worst-case rate.
  If that exceeds a third of the remaining budget, resize the JOB, not the
  estimate.
- **Express budgets in VM-hours**, the thing measurable in real time.
  Dollars are a lagging indicator here.
- **Arm `scripts/cloud_budget_guard.sh` with every fleet launch.** Verify
  terminal resource state after cancellation; process/API/network failure can
  prevent the monitor from enforcing its intended time limit.
- **Re-derive spend daily** from `gcloud batch jobs list` durations x VM
  count x rate. Do not wait for the console.
- **Use the home box first.** Recorded September 2 build measurements were
  about 2.3 symbols/hour locally versus 1.98/hour for one packed 4-VM fleet.
  New family grids/caches need a fresh pilot; historical pace is not an ETA
  for the expanded campaign.
- **Deleting stale Artifact Registry images is now a cost item**, not
  housekeeping: ~12 TF-heavy tags at ~$0.10/GB/month.

## Data access — September 5 probes

**Massive Options Advanced upgraded 2026-09-05**, with the following recorded
provider probes. They describe those observed dates/entitlements; a future
campaign still needs local coverage and representative provider checks:
- **Option minute/day aggregates: full history** — REST `/v2/aggs` returns
  1-minute bars for SPY contracts in 2019, 2020, 2021, 2022, 2023 (checked);
  flat-file `minute_aggs_v1` and `day_aggs_v1` GetObject succeed for 2017,
  2019, 2021, 2022 … 2026 (bucket lists 2014→).
- **Trades: full history** — `trades_v1` flat files 2017→ readable (8–67 MB
  gz/day); REST `/v3/trades/{ticker}` returns 2021+ (checked).
- **Quotes: 2022-03-07 →** — `quotes_v1` flat files 2022→ readable but
  **85–140 GB gz per day** (not bulk-crawlable); REST `/v3/quotes/{ticker}`
  (per contract, `timestamp` filters, limit ≤ 50,000, `next_url`) 2022+.
- **Snapshots real-time** on Advanced (`/v3/snapshot/options/{underlying}`:
  greeks, implied_volatility, open_interest, last_quote, last_trade).
- **WebSocket** options aggregates/trades/quotes real-time on Advanced;
  wildcard subscriptions are Business-only. Unused: the system decides on
  closed 15m bars (memory: data-provider-subscriptions).
- **MCP**: `claude mcp add --transport http massive https://mcp.massive.com/`
  (OAuth, no key; mirrors entitlements).

*Pre-upgrade record (Starter, until 2026-09-05):* options history reached
~2 years back (403 before ~mid-2024), on REST *and* flat-files — the S3
bucket listed 2014→ but GetObject was date-gated.
- **Minute aggregate flat files remain the bulk-history path**: the earlier
  campaign observed ~33 MB gz/day covering OPRA contracts, quota-free
  (`files.massive.com`, bucket `flatfiles`,
  `us_options_opra/minute_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz`, s3v4).
- Recorded provider probes obtained Alpaca 1m underlying history back to
  2017. This does not establish completeness of every local cached symbol;
  reconcile the known year-end holes before a deeper-data campaign.
- **Alpaca Algo Trader Plus since 2026-09-05**: SIP real-time (the free
  tier already served SIP history but withheld the newest 15 minutes —
  cache bars are SIP, verified), 10,000 REST calls/min, unlimited stock
  websocket symbols, OPRA options websocket (≤1,000 quote symbols), News
  + screener endpoints; Alpaca option bars only reach 2024 → Massive stays
  the options-history source. The `.env` keys are PAPER keys (options
  level 3); live-account keys would be a separate decision.
- Existing v5/v6 label windows remain frozen research choices. Advanced
  enables deeper option history; a v7 expansion must acquire/reconcile raw
  data, PIT membership and surface coverage before making deeper-label claims.

## Scale lessons (paid for; don't rediscover)

- The historical v31 **mark stream is ~88M rows** (489k trades × ~180 bars held).
  Assembling it via `pd.concat` peaked ~9 GB and failed on the old box; the
  shipped path streams shard-by-shard through a `ParquetWriter` (peak
  ~0.2 GB) with `trade_id` as a **lexically-pinned categorical** (101 → 19
  bytes/row). Anything else that loads the whole sidecar needs the same care.
- Parquet returns dictionary categories in first-appearance order — pin
  category order explicitly or sort order silently depends on assembly order.
- **The home box beats a 4-VM cloud fleet at this workload** (measured
  2026-09-02): box 2.33 symbols/h from 3-5 workers vs 1.98/h from 4
  spot VMs running 20 packed tasks — ~2.1 h per symbol on a Ryzen worker
  vs ~10.1 h on a packed cloud task, ~5x per worker. The 9850X3D's 3D
  V-Cache suits this (the builds re-read the same chain/bar working set);
  packed cloud tasks instead contend for one VM's memory bandwidth.
  Corollary: treat the box as the workhorse and cloud as the accelerator
  you pay ~$0.50/symbol for, not the other way round.
- **The universe read-path optimization shipped September 5.** Providers
  read per-underlying parquet slices; new derivations sort by underlying for
  row-group pruning. Recorded chain checks matched 200/200 samples including
  order, with ~205 to 0.74 ms per call. Existing on-disk universes may remain
  unsorted until separately regenerated/sorted; inspect before assuming
  pushdown efficiency. No new provider subscription was needed for this fix.
- **Build workers are memory-sensitive.** The old full-universe duplication
  was fixed; earlier 5.4 GB/RSS measurements describe that campaign, not
  today's guaranteed footprint. Measure the expanded pool before autosizing.
- Historical big-name builds took ~33 min/symbol/shard, with a packed v5
  symbol sometimes taking ~8h (ten families × DTE grid versus v31's five).
  Use representative new-campaign measurements for leashes/stall alarms;
  burst extrapolations and earlier pool timings are unreliable.

### GCP Batch fleet sizing (all four paid for during the v5 campaign)

- **Batch packs by `cpuMilli` and OVERCOMMITS `memoryMib`.** Asking for
  12 GiB does not stop 8 tasks landing on a 64 GiB VM. Eight × ~10 GB of
  cache overflowed the page cache and the fleet did ONE symbol in 11h.
  Pin the packing with `CPU_MILLI` (1500 → 5 tasks on an 8-vCPU VM).
- **Persistent-disk throughput scales with disk SIZE.** A 70 GB
  pd-balanced boot disk is ~20 MB/s — five tasks staging 10 GB each cost
  ~1.4h per slot cycle. Fix is a **local-SSD scratch shared per VM**
  (`LOCAL_SSD=1`): one cache copy at NVMe speed behind an flock.
- **COS's root filesystem is read-only** — a Batch `volumes` mountPath of
  `/mnt/ssd` fails with exit 125 (`mkdir: read-only file system`). Host
  mounts must be under `/mnt/disks/`; bind-mount into the container at
  whatever path the code probes.
- **Spot machine families are NOT interchangeable, and none are safe
  alone.** e2 was reclaimed 3× in 5h; n2 and c2d each ran ~12h clean then
  swept during US business hours; c2d's pool went dry for 3h while n2
  filled instantly. A twin fleet on two families can improve availability;
  budget aggregate billed VM-hours and verify actual concurrency rather
  than assuming the second submission has no incremental cost.
- **Never confirm an image from `gcloud builds list`** (the list-and-pick
  trap again). A silent Dockerfile-copy failure plus a stale list entry
  launched 441 tasks against a nonexistent tag — 148 instant failures on
  `manifest unknown`. `submit.sh` now gates on
  `artifacts docker images describe <IMAGE>` and refuses to submit.

## Production ops — Hetzner server

Deployment details below reflect the 2026-09-08 inspection and fixes
([review](docs/reviews/2026-09-08-server-ops-fixes.md)). The server runs the
compatibility branch `ops/server-alert-readiness-20260906` (997d668), which
carries live-path source that `main` does not have yet (scanner, v4_scan,
barstore, alert_batches, heartbeat, feeds, logging_utils, config). Deploying
`main` there would regress those fixes: merge the ops branch into `main` first.
The audit merge did not regenerate bundles; plan compatible source and
regenerated verified bundles together. All experts send alerts; historical
“real” labels do not mean broker auto-execution.

- **Host**: Hetzner CX33 (4 vCPU / 8 GB), Helsinki, `62.238.20.66`,
  Ubuntu 24.04, ~$9.59/mo. SSH `mrhea@` with the home box's
  `~/.ssh/id_ed25519` (that key is Hetzner-only; GitHub auth is `gh` over
  HTTPS). Repo at `/home/mrhea/HealysBacktester`.
- **[v5] expert (deployed 2026-09-05, paper seat — alerts only, like every
  expert)**: the same `nn_meta.live.v4_scan` module run under
  `NN_META_POOL=v5`. It scores with `nn_meta/model_final_v5/` (nn×40,
  ev/0.05, historically cleared the pre-audit risk-aware gate — DECISIONS
  2026-09-04; this is not a current corrected verdict), reads the
  frozen spec `nn_meta/artifacts_v5/baseline_spec.json` (441 PIT-universe
  symbols) and the surface/universe caches in `nn_meta/data_cache_v5/`
  (seeded by rsync from the box 2026-09-05; refreshed by the Sunday v5
  cron lines like v3/v31). Alerts are titled `[v5] …`; its state files are
  `nn_meta/live/.v5_*.json`; log `logs/v5_cron.log`; it appears as a
  `[v5]` section in the panel digest and the heartbeat. One pass scans
  441 symbols (~2 min; v31's 120 take ~35 s). Promotion beyond paper is a
  user decision after a forward record beside V118.
- **Deploy = `git pull origin main` over the read-only deploy key. NEVER
  scp** — an untracked scp'd file once wedged pulls for days, silently.
- **Live feeds (since 2026-09-05)**: two daemons, `nn_meta.live.feeds.
  stock_stream` (Alpaca SIP 1m bars, 443 names → `nn_meta/live/feeds/data/
  1m/<SYM>/<day>.parquet`, backfills today on start) and
  `nn_meta.live.feeds.option_stream` (OPRA quotes for
  `nn_meta/live/feeds/data/option_watch.json`, ≤ 1,000 contracts →
  `option_quotes.json`). Started by `@reboot` cron lines and restarted by
  5-minute `pgrep -f "feeds\.<name>$" || nohup` watchdog lines (no sudo on
  this host). The pattern is ANCHORED since 2026-09-08: the earlier bracketed
  `"[f]eeds.<name>"` matched the watchdog's own `sh -c` line, because that
  line also contains the restart command `-m nn_meta.live.feeds.<name>`, so
  a dead daemon was never restarted (observed: the option stream stayed down
  through a watchdog cycle after being killed). Logs `logs/feeds_stock.log`,
  `logs/feeds_options.log`; heartbeats `stock_stream.heartbeat.json` /
  `option_stream.heartbeat.json` (in the 17:00Z digest; stale > 5 min during
  RTH = ⚠️). The option stream IDLES (`state: idle`, no CPU) until
  `option_watch.json` names a contract — before the gate it busy-waited a
  full core for three days on an empty list. Contracts get there from the
  alert path: `scanner.register_alert_contract` resolves the ~ATM/~DTE
  advisory to a listed OCC symbol via `nn_meta/live/feeds/contracts.py`
  (reads the pool's `contracts.parquet`). Loaders read today's bars from the
  store when the heartbeat is ≤ 3 min old, else forced REST; a 15m bucket
  with missing minutes is accepted when SPY/QQQ streamed those minutes
  (`barstore.ALIVE_REFERENCE`), otherwise it falls back to REST.
  Health: `pgrep -f 'feeds\.stock_stream$'`; validate timestamps and data
  coverage too. Historical process/RSS counts are diagnostic context, not a
  parity gate.
- **Cron (UTC — this cron ignored `CRON_TZ` in the recorded inspection)**.
  Expert passes fire one to three minutes after the 15m bar closes by pool
  (2026-09-05): v5 at `1,16,31,46` (`--workers 3`), [v4] and [v31] at
  `2,17,32,47` (`--workers 2`), v3 at `3,18,33,48` (`--workers 1`).
  - `3,18,33,48 * * * *` live scanner: `NN_META_POOL=v3 … run_live --once --nn`
    → `logs/live_cron.log` (self-gates to RTH)
  - `2,17,32,47 * * * *` **[v4] expert** (paper 2026-08-16 → alerts 2026-08-24,
    V118 bundle gbt/ev/0.05): `NN_META_POOL=v31 … nn_meta.live.v4_scan
    --once` → `logs/v4_cron.log`. The scan refuses to alert unless the
    bundle verifies AND is gate-eligible. Prepare rollback from the actual
    current cron/source/bundle snapshot; an August backup predates later
    experts/feeds and is not a panel-wide rollback. Needs
    `nn_meta/data_cache_v3/{surface_daily,
    underlying_daily}.parquet` on the host (rsync'd; gitignored path,
    refresh occasionally).
  - `2,17,32,47 * * * *` **[v31] expert** (since 2026-08-16): `NN_META_POOL=v31 …
    nn_meta.live.run_live --once --nn` → `logs/v31_cron.log`. Legacy scorer
    path (prices the frozen-DTE contract live via the hybrid provider);
    `[v31]`-labeled alerts; own dedupe file `.alert_state_v31.json`.
    Rollback = delete the line.
  - `0 10 * * 0` + `30 10 * * 0` **weekly universe refresh** (since
    2026-08-16): `download_universe --universe-only --live-horizon 120` for
    the v3 pool then the v31 pool → `logs/universe_refresh_*.log`.
    **Keep each pool's bars+surface steps in ONE cron entry** (now the
    `run_refresh.sh` script) — splitting them into separate times invites the
    refresh/compaction swap racing the surface build's glob-then-open. This is
    what keeps the live chain's expiries ahead of the calendar — the frozen
    research window does NOT roll forward on its own, and the chain
    silently empties ~45 days after the last refresh without it.
  - `10 20 * * 1-5` **[v4] watchlist digest** (since 2026-08-24):
    `NN_META_POOL=v31 … v4_scan --digest` → one Telegram
    top-10 of the day's scored signals regardless of threshold, plus the
    seven-day entry-cohort underlying-direction hit-rate (watchlist vs
    alerted subset), not seven days of resolved option P&L. No model load;
    state `nn_meta/live/.v4_watchlist.json`
    (gitignored), 21-day retention. Rollback = delete the line.
  - `5 * * * *` FA collectors (`fa.collect`) → `logs/fa_cron.log`
  - `30 12 * * 1-5` trending digest (8:30 ET summer) → Telegram
  - `0 17 * * *` scanner heartbeat (noon CT summer): one line per expert
    (v3/v4/v31/v5) — passes/alerts + NEW crashes per cron log since the last
    heartbeat, plus missing/stale-log warnings during RTH — silence = quiet
    market, not "is it dead?". Baselines in the gitignored
    `nn_meta/live/.heartbeat_state.json` (old single-log schema migrates in
    place; first heartbeat per log prints "baseline set"). Since 2026-09-08
    the head also flips to ⚠️ on: > 50 scanner ERROR lines today, an options
    heartbeat reporting 0 contracts during RTH, any pool's
    `surface_daily.parquet` older than 8 days, or a non-zero exit recorded
    in `logs/refresh_status/<pool>.json`; a `surfaces: v3 2d · v31 2d · v5 …`
    digest line shows the ages.
  - `* * * * *` **top-five dispatcher** (since 2026-09-08 a.m.,
    `NN_META_ALERT_TOP_N=5 … nn_meta.live.alert_batches` →
    `logs/alert_batches.log`): the four experts enqueue entry alerts into
    `nn_meta/live/.alert_batches.sqlite3` keyed by 15-minute cycle; after all
    four completion markers (max 5 min after the first, deadline 12 min after
    bar close) it sends the five highest P(win) — one slot per symbol+side
    since the evening fix — and one overflow notice with a button / "yes"
    reply for the remainder summary. Floors: v5 > 0.55, v4 > 0.51 (strict).
    Cron-line env `NN_META_ALERT_TOP_N=5` on every scan line is what routes
    alerts into the queue; without it an expert sends directly.
  - `* * * * *` **EOD panel tick** (since 2026-09-06, `scripts.eod_panel_tick
    --run`): calendar-aware; prewarms, then delivers one confirmed end-of-day
    panel at close − 5 min → `logs/eod_panel.log`.
  - `0 11/12/14 * * 0` **weekly bars + surface refresh** per pool
    (`scripts/run_refresh.sh v3|v31|v5` since 2026-09-08): download recent
    bars with `NN_META_DOWNLOAD_WORKERS=6` (the 16-worker default was killed
    on this 8 GB host at 84% of the 1.3M-contract v5 run on 2026-09-06, and
    the `&&`-chained surface build silently never ran — v5 then scanned on a
    14-day-old surface), then `build_surface`, both inside ONE script so the
    ordering guarantee below still holds; exit status to
    `logs/refresh_status/<pool>.json`.
  - `7 4 * * *` **log rotation** (`scripts/rotate_logs.sh` →
    `deploy/logrotate/healys.conf`: daily or 100 MB, 14 kept, compressed,
    copytruncate because the feed daemons hold their logs open; state in
    `~/.logrotate.healys.state`). The heartbeat detects rotation and resets
    its counters.
  - `*/5` dead-man check (`~/bin/deadman_check.sh`, outside the repo on
    purpose) watching home-box job heartbeats.
- **Reverse dead-man (HOME box → server, added 2026-08-28)**:
  `healys-server-deadman.timer` — installed as a **user timer**
  (`~/.config/systemd/user/`, linger enabled for healy, so it survives
  logout/reboot; no sudo was available remotely — deploy/systemd/ keeps
  the system-unit copies if anyone prefers that install). Hourly, runs
  `scripts/server_deadman.sh` — SSH probe; pages Telegram after 2
  consecutive misses, re-pages every 12h, announces recovery. Built after
  the 2026-08-27/28 outage: a **billing lapse null-routed the server's IP
  at 13:32Z Thu while the box kept running** — cron fired all along,
  Alpaca/Telegram just failed, so "no heartbeat" looked like a quiet
  market for ~31h. Zero alerts fired on stale data (scanners fail closed).
  Fix path that time: pay invoice → Hetzner unblock request → power-cycle.
  Keep the payment method current; Hetzner blocks the IP without powering
  the box off.
- Server `.env` = home `.env` + `FA_SKIP_COLLECTORS=stocktwits` (StockTwits
  Cloudflare-blocks datacenter IPs — the home box collects it hourly via
  `healys-stocktwits.timer` and rsync-pushes the archive).
- **Rollback must preserve compatible source and artifacts.** Dropping
  `NN_META_POOL=v3` selects v2; it is not a valid default rollback when its
  bundles lack the current contract. The older `_st.py` selftest was absent
  in the August inspection; inspect `logs/live_cron.log`, closed-bar timestamps
  and verified bundle state instead.
- State on the server that is NOT in git: `.env`, `fa/archive/`, the 5 root
  parquets of `nn_meta/data_cache/` (scanner needs `surface_daily.parquet`),
  the alert queue `nn_meta/live/.alert_batches.sqlite3`, per-expert
  `nn_meta/live/.<expert>_no_bars.json` (names that returned no bars — X,
  WBA, SWTX, SAVA, SATS as of 2026-09-08 — skipped and rechecked weekly
  instead of costing two REST calls and four ERROR lines every pass),
  `logs/refresh_status/`, `logs/ops/*/crontab-before.txt` rollbacks.
- **Cron edits go through `scripts/configure_cron.py`** (preview without
  flags, `--run` to install; idempotent; backs up to `logs/ops/ops-fixes-<ts>/`).
  It owns the scan-line env `TF_CPP_MIN_LOG_LEVEL=2 BACKTESTER_CONSOLE_QUIET=1`
  (no TensorFlow banners; the console filter in `utils/logging_utils.py`
  keeps WARNING+ and `[live]`/`[v4-scan]`/`[notify…]`-tagged lines and drops
  the per-symbol vectorbt chatter that made `v5_cron.log` 93 MB/day; print()
  pass summaries the heartbeat counts are untouched). `logs/backtester.log`
  keeps WARNING+ only (`BACKTESTER_FILE_LOG_LEVEL=INFO` to widen for a
  debugging session) — it is what the heartbeat scans for `- ERROR -`.

## Home-box scheduling (systemd)

- StockTwits collection is documented as installed historically, with later
  OS-restore notes requesting timer checks. Inspect current user/system units
  and last runs before asserting it is active. The intended timer is hourly
  and `Persistent=true` to catch up after downtime.
- Committed, not installed: `healys-boot-restart.service` (unattended
  long-job recovery — optional; see `deploy/systemd/README.md`).
- Auto-suspend must stay **off** on this box — COSMIC's idle suspend once
  silently killed the hourly collector for a night.
- Historical note: the box had a long kernel-memory-corruption investigation
  (BIOS/DRAM/XMP/sustained-load all ruled out). **Declared a non-issue
  2026-08-15 — do not spend time on it.** The checkpoint-everything and
  commit-often habits it forced are worth keeping anyway. A leftover
  diagnostic `turbo-cap.service` may still be installed system-side; safe to
  `systemctl disable --now` and delete.

## The documentation system itself

Defined in `CLAUDE.md` (read that first). Quick map: `ROADMAP.md` overall
goals → `TODO.md` current phase → `HANDOFF.md` session state
(`handoff-history/` archives) → this file for durable notes →
`docs/DECISIONS.md` dated decisions → `docs/EXPERIMENTS.md` run verdicts →
`docs/specs/` designs → `docs/v31_run_history.md` archived chronology.

## September 5 corrected research preparation

- `nn_meta.download_data._load_chunked` takes inclusive calendar start/end
  dates. Vendor request endpoints are midnight: adjacent requests meet at the
  same exclusive boundary, and the final request reaches the midnight after
  `WINDOW_END`. Subtracting one day and advancing past it drops full sessions.
  Existing caches require repair; a downloader fix does not backfill old bytes.
- `NN_META_CAMPAIGN=<simple-name>` isolates derived output below
  `nn_meta/campaigns/<name>/<pool>/`. Raw caches remain shared read inputs.
  v5/v6 final bundle paths belong to the selected pool. Use
  `scripts/run_research_local.sh` for previews and explicit local stages;
  immutable source/data/runtime fingerprints refuse incompatible resumes.
  Archived additive/cloud launchers are not corrected-campaign instructions.
- Two-way option/underlying date coverage catches the five observed chunk-end
  holes that the old one-way preflight missed. It still cannot detect a session
  absent from both archives or establish complete per-symbol coverage.
- `indicators.tradingview_registry` verifies all thirteen selected source
  identities and generates fixture fingerprints for scoped implementations.
  Source pinning/local tests do not establish exported Pine parity or admit
  these families to existing proposal pools.
- `nn_meta.live.contract_preview` is a captured-snapshot preview, with no
  network/order/notification side effects. A reported 100 shares per contract
  does not prove standard deliverables; contract-reference verification and
  offline selection parity remain required before execution integration.

First-batch evidence and remaining gaps:
[readiness review](docs/reviews/2026-09-05-readiness-milestone.md).

## Raw stock basis and option tick continuation

The current build contract is `2026-09-06-raw-spot-v3`. Adjusted technical
OHLCV and raw contemporaneous option-selection spot are separate inputs.
`nn_meta.price_basis` requires explicit raw provider/feed/interval provenance;
renaming an adjusted file does not satisfy it. Raw `underlying_15m_raw.parquet`
must cover every technical timestamp used for option selection. Raw
`underlying_daily_raw.parquet` supplies spot for strike filtering and implied
volatility; adjusted daily returns still supply volatility/beta features.
Every roll selects after a known bar close and fills in a later bar.

The wide v5 archive's universe was derived from **all observed contracts** in
the root-filtered option dayframes. Preserve that broad chain. It was the
surface's daily option summaries that had an adjusted-spot moneyness filter.
`v3.derive_contracts --cache INPUT --output-cache NEW_OUTPUT` rebuilds those
parts with raw spot and preserves complete first-seen contract identities.
Explicit old-root raw history is required when a current ticker does not
cover its earlier identity. Output tags and hashes prevent mixing old/new
surface parts or silently narrowing the observed chain.

`NN_META_DATA_CANDIDATE=<name>` selects a separate staged cache and requires
a named v5/v6 research campaign. `scripts.repair_underlying_cache` records
provider settings, calendar boundaries, issuer/listing exclusions, observed
coverage, reference comparisons and immutable input/output evidence. Sealing
must finish after all repairs and context derivations; a new campaign name
does not waive the seal. Original caches and paused research artifacts stay
preserved. Legacy Batch transport rejects these named paths until its
staging/output transport is implemented; use the local launcher.

Named historical providers write per-contract option slices only under
`RUNS_DIR/provider_cache`. Existing `DATA_CACHE/bars_*` files are read-only
fallbacks; never materialize new contract files into a sealed candidate.
The first raw-price pilot exposed this old provider behavior. Its additional
files were quarantined after every original payload was verified, restoring
the exact original inventory without changing the seal. The aborted scope's
freeze shard is ineligible. A fresh campaign binds the corrected source.
Contract lifetime lookups now index one underlying slice and retain a ticker
predicate fallback for old roots catalogued under a renamed symbol.

V6 live aggregation requires a captured exchange calendar with explicit
coverage dates, holiday omissions and early closes. The default location is
the selected cache's `exchange_calendar.json`; use `NN_META_SESSION_CALENDAR`
for a deployed calendar. Dates beyond coverage raise rather than guessing.
`stock_stream --spec PATH` includes a deployed campaign's frozen universe.
Stock restart backfill requests raw SIP bars and reruns after reconnects.
Feed heartbeats distinguish received data, reconnecting/stopped processes,
malformed/future timestamps and custom store paths. These code checks do not
establish full-session stream/REST parity.

`scripts.capture_option_ticks` previews by default and downloads only explicit
contracts/windows with `--run`. It verifies complete pagination, preserves
integer nanoseconds and raw trade multiplicity when identifiers are absent,
and binds compressed/raw data hashes, implementation and feature policy.
`options.tick_features` computes descriptive spreads, quoted-size imbalance,
quote freshness, reported trade volume/VWAP and an explicitly gated quote-test
signed-volume estimate. Empty/unknown condition codes are unsigned by default.
Ambiguous simultaneous quotes, stale receipt-time quotes and mixed contracts
cannot silently supply a trade's direction. These are research inputs, not
observed fills or true aggressor labels.

The existing OPRA daemon can record quotes and trades with `--record-ticks`;
[journal runbook](docs/specs/OPTION_TICK_JOURNAL.md) covers subscription limits,
raw message preservation, receipt precision and failure/restart behavior.
Alpaca condition strings and event clocks are not interchangeable with Massive
condition integers/SIP timestamps without a validated adapter. Neither a
healthy socket nor the historical [two-contract pilot](docs/reviews/2026-09-06-option-tick-pilot.json)
proves complete training coverage or live parity. Quote/trade feature admission,
costed execution, full-session comparison and compatible bundle rollout remain
separate checks.

## Expanded v6 freeze boundary (September 6)

`scripts/run_freeze_v6_local.sh` now delegates a fresh expanded freeze to the
validated campaign runner. It requires the repaired candidate and an externally
hashed feature manifest; it no longer inherits old v5 freezes or runs only
Keltner/BBW. `NN_META_V6_EXPANDED=1` selects the 20-family/TV13/tick contract.
Use the input runbook above. The old raw-options pilot recovery descriptor is
`.retired`; its actual exit remains1 and its artifacts are preserved.

Historical tick request selection must precede option outcomes. It uses raw
bar-close spot, prior-date observed catalogue membership, deterministic strike
selection and the same policy as labels. A live provider that ignores as_of
cannot supply that historical evidence. The richer candidate interface retains
selection/request/coverage audit columns and requires an explicit adapter.
The historical sealed-input replay path does not establish live receipt latency
or Alpaca/Massive condition equivalence.

## Delayed V6 option-context publication

A MASSIVE `NoSuchKey` for the previous session blocks fresh V6 data, entries
and ordinary strategy exits; expiry fallback remains on the exception path.
Do not advance the data pointer or weaken the freshness check. The separate
`healys-v6-context-retry.timer` polls weekday :08/:38 UTC between 09 and 19
hours. `scripts/retry_v6_context.py` checks every missing completed session,
then requests the existing refresh only when producer/refresh are idle.
`waiting_for_provider` is not recovery. Verify refresh success, fresh pointer,
accepted producer cycle and relay/delivery. Keep this helper independent of
activated numerical source; reinstall its two committed systemd units if
rebuilding operational timers. [Incident](docs/reviews/2026-09-15-v6-paper-health.md).

## V7 historical source and pilot traps (September 16)

- Alpaca SIP quote sizes switched from round lots to shares November 3, 2025.
  Require dated unit evidence; multiplying all historical sizes by 100 is wrong.
- A stock trading date may be a settlement bank holiday. Count T+1/T+2 from
  the original event, using later captured settlement dates; do not roll T first.
- Official calendars can conflict or URLs can be mutable. Captured FINRA 2023
  annual notes conflict with later indexed DTCC Veterans Day guidance. A Nasdaq
  URL naming 2025 currently serves a 2026 PDF; inspect bytes and publication
  vintage, not URL year. Original DTCC 404s are not successful source captures.
- Recursive source traversal can spend minutes inside archived data trees. V7
  model component pilots bind loaded project dependencies plus all V7 code;
  full-campaign provenance remains separate and unchanged. Pilot receipts are
  not full-universe admission. See the September 16 stock-quotes/model reviews.

### V7 full daily surfaces and endpoint calendar

`build_v7_surfaces.py` uses verified raw stock daily shards and exact active
Massive daily/audit receipts. It requires a separate receipt-backed Alpaca
availability calendar that agrees across the original calendar's entire
coverage and extends beyond the study endpoint. Do not rewrite the stock
calendar or infer the next session from weekdays. The extended exchange
calendar does not resolve settlement/exercise-calendar evidence. Full raw
surfaces retain missing values and literal ticker roots; they establish neither
identity outside membership nor option deliverables. Causal daily/context
integration is still required. See the September 16 full-surfaces review.

### Current option-risk policy (September 16–17)

The later user choice is arithmetic `(bid + ask) / 2` for simulated option
entries, exits and marks; retain the separate 0.15% per-side cost allowance.
Option-midpoint loss stops are 7.5% for V6 and 12.5% for V7, measured from entry
premium. Retain strategy exits and the ITM expiry cutoff 15 minutes before the
option class regular close. Last trade is reference only. The earlier
provider-midpoint and ask/bid descriptions are historical. The actual FIG stop
and remaining V6 quote-health limitation are documented in the three-day report;
this note is not a new deployment or a declaration of V6 health.

### September 16 initial midpoint paper amendment (historical)

User-directed `option-midpoint-paper-v1` applies to V6 and V7 simulated option
entries, exits, rolls and marks. Use a valid provided midpoint, otherwise bid/ask
average; last trade is reference only. Preserve quote sides, source and fees.
V6 runtime commit `4fe7e5f` is activated on home; closed legacy history is
preserved. Never silently mix an old ask entry with a new midpoint exit: existing
open paper legs require the audited idempotent `migrate_midpoint` transition.
The September 16 deployment had zero open legs. Activation changes are limited
to reviewed pricing modules; all other runtime sources must retain prior hashes.
See `docs/reviews/2026-09-16-midpoint-paper-pricing.md`.

### V7 causal daily returns and context

`nn_meta/v7/causal_daily.py` uses adjacent raw closes and only reviewed factors
effective at the current session open. Missing sessions or identity continuity
breaks invalidate returns and restart rolling warmup; nullable identity spans
retain explicit unknowns. Do not collapse the calendar to observed rows. All ten
daily features retain next-session availability and observed surface missingness.
Caller-supplied action/identity IDs are bindings, not evidence of completeness;
the full builder still needs reviewed action/no-event and continuity inventories.
The older `daily.daily_context` adjusted/filled component is not the new causal
path. Use the fresh `v7-stock-daily-20260916-midpoint` and
`v7-surfaces-20260916-midpoint` outputs after the midpoint manifest amendment.

### V7 corporate-action reconciliation traps

Alpaca corporate-action requests are bounded by **process date**, not ex-date.
An absent record is not proof of no effective event; `data_quality=all` also
retains incomplete records. `action_inventory.py` keeps all symbol roles, including
acquiree/source/new symbols and nested movement legs. Massive split-endpoint rows
include stock dividends and apparent spin-off adjustment ratios: reported ratios
are not automatic proof of share delivery. Never sum or deduplicate cash records
just because they share amount/date. DVN September13,2024 has three $0.22 Massive
rows and one Alpaca row, while the original issuer confirms $0.44 total. Apply
the reviewed replacement to the **whole event group once**, retaining all source
IDs. See the September16 action-inventory review and immutable DVN exception.

### V7 publication content versus historical version

The generic cash body matcher requires amount and explicit-year record/pay dates
in one paragraph, a single issuer, and a captured update clock before the ex-date.
Do not join unrelated HTML blocks or infer years automatically. Current issuer
HTML can retain an old publication date while carrying a much later modification
clock: all 18 Apple releases captured September 16 show August 19, 2026 updates.
This does not establish changed cash terms, but does require keeping historical
version proof separate from current issuer confirmation. The finite Apple review
corroborates all amounts against dated captured news, with 17 record/pay date
pairs; May 2023 has amount only. See the cash-publication review.

### Reviewed cash event consumption

`cash_actions.compile_cash_actions` replaces the whole symbol/effective-day cash
group once, requiring exact provider IDs/hashes. The normalized review total is
not added to original provider components. A simultaneous split/complex action
fails this cash-only compiler and requires combined-event review. Prior close
must come from the exact preceding captured exchange session with the same
eligible security ID. Compiled events do not establish full-security continuity
or no-event coverage; unresolved inventory must remain explicit upstream of any
full daily/feature admission. See the September 16 cash-action integration review.

### V7 ordinary-action admission (September 17)

The user accepted matching ordinary provider terms as historical reconstruction
inputs from the effective session. `ordinary_actions.py` and
`compile_v7_ordinary_actions.py` implement the bound policy in
`docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json`. Original publication
reviews retain precedence; duplicate, combined, complex and conflicting records
remain explicit. Exact dated security continuity and observed cash-event prior
closes are still required.

`ReconstructionAction` subclasses `PriceAction` for the existing causal consumers.
Its `available_at` equals the effective open **by assumption**, while publication
availability remains null and `publication_verified` remains false. Keep the
additional policy/basis fields when serializing; `proposal_store.build_features`
already retains them via dataclass serialization. Use `ordinary_actions.price_action`
to load compiled event envelopes without erasing the distinction. Do not label
these records as publication verified or use them to establish no-event intervals,
cash entitlements or option deliverables. See the September 17 ordinary-action
review for the full compilation census and consumer limits.

### V7 exact-date share-class resolutions (September 17)

`share_class_history.py` and `resolve_v7_share_class_history.py` consume finite
reviews in `V7_SHARE_CLASS_IDENTITIES_20260917.json`. Each exact-day record must
share a positive share-class FIGI and identical ticker, primary exchange, type,
market, locale, currency and issuer CIK with an earlier captured scoped listing.
Both must be active US listings; a competing scoped composite ID cannot be merged.
Missing CIK is allowed only when both original records omit it. No future anchor,
name similarity, filled price or absent listing establishes identity.

The canonical candidate panel is temporary. Original captures remain unchanged;
the output retains `provider_composite_figi`, `resolved_share_class_figi`,
`identity_resolution` and its review hash separately from the canonical security
ID. Rebuild from the original selected history plus cumulative finite reviews;
the script rejects an already resolved baseline to prevent erasing earlier evidence.
Resolved zero-observation dates remain zero-observation dates. This identifies
the instrument only; action admission, no-event coverage and held entitlements
remain separate. Recompile actions after a history change: restored continuity
can rebind event IDs even when all factors and clocks are unchanged. See the
[share-class review](docs/reviews/2026-09-17-v7-share-class-identities.md).

### V7 daily identity capture and continuity

The production proposal builder now requires `--action-coverage`, produced by
`audit_v7_action_coverage.py`. `admitted_history.bind_history_coverage` verifies
the bound policy, exact required sessions, original dependencies, stock routing
and compiled event IDs. The accepted no-event assumption is in
`V7_NO_EVENT_ADMISSION_20260917.json`; preserve it in feature-store declarations
even when no chart actions occur. Event-publication fields must also survive:
load compiled envelopes with `ordinary_actions.price_action`, not `PriceAction`
directly. A component pilot may still build features without a complete-history
admission, but such a pilot does not pass the production builder's input guard.

`review_v7_other_instruments.py` retains finite unrelated ticker-reuse treatments
separately from chart events. Rebuild that artifact against the current action
set before producing coverage; the original-record partition must reconcile.
`extend_v7_action_inventory.py` appends the named process-date-tail capture,
retaining original records and rejecting revised existing IDs. The effective-date
scope does not change when a scheduled process/payment date lies later.

`extend_v7_security_history.py` and `history_supplement.py` fill only missing
source selections with exact-identity observed daily data, preserving prior
identity provenance, original candidate counts/source status and the full calendar
grid. GAP 2025–2026 uses this path. Rebuilding from selected rows alone cannot
recover original candidate multiplicity; preserve that fact explicitly.
Pass `--raw-supplement` to the proposal builder when needed; its raw receipt must
already be bound through a selected daily declaration. Ambiguous overlapping raw
captures cannot silently replace the original data.

Finite unchanged-common-share ticker reviews use `review_v7_renames.py` and
`V7_COMMON_SHARE_RENAMES_20260917.json`. Supply `--renames` to the coverage auditor;
it retains identity-event IDs separately from price events and reconciles every
original record. A reviewed rename never clears other unresolved records.
`review_v7_other_renames.py` extends finite unrelated-instrument treatments with
positive adjacent foreign identities and a distinct scoped share-class witness.
The coverage auditor combines all treatment references against the original
inventory; do not use the last artifact's pending list as an implicit override.
`PhysicalLedger.apply_stock_rename` requires the exact effective clock and updates
stock symbols without changing cash, quantity or settlement; pass reviewed events
as `physical.renames` for chronological portfolio scheduling. Open option or
merger phases reject stock-only notices before any mutation. Primary dates,
adjacent original identity witnesses and source receipts remain mandatory.

Daily listed identity capture restricts primary exchanges to ARCX/BATS/XASE/XNAS/
XNYS and validates every response. These are metadata requests, not stock-price
requests or publication-safe fundamentals. `--max-shards` bounds one invocation
while retaining the full acquisition declaration. Source hashes are immutable
across resumption: do not edit the running capture or bound dependencies. Poll
the exact process handle; resume only after a confirmed terminal failure. Exact
daily identities do not establish corporate-action/no-event coverage. The panel
retains absent/missing/colliding identities and breaks continuity instead of
propagating monthly snapshots. See the September16 daily-identities review.

### V7 build-first operating priority (September 16)

The 250 GB acquisition budget is a ceiling, not a target. The user stopped broad
reference expansion after the current captures completed. Before adding any new
capture, identify the exact missing input consumed by the full build. Use retained
provider/action/identity evidence first; optional issuer or reference completeness
must not become an open-ended prerequisite. Preserve explicit unresolved cases
and finish the executable feature/proposal, execution/label, assembly and training
path. Current full identity/history artifacts and terminal job state are in HANDOFF.

### V7 reviewed source routes (September 17)

`compile_v7_source_routes.py` extends the existing alias artifact with reviewed
exact-session routes, including a noneligible day needed by feature history.
Pass its output directly to `build_v7_security_history.py --aliases`. It requires
matching exact-day FIGIs for both listings, actual selected-source observations,
and bound publication evidence available before the open. It does not establish
membership, corporate-action adjustment or option-deliverable continuity.
The FISV/FI June 7, 2023 route is in `V7_SOURCE_ROUTES_20260917.json`.

The full builder binds each source-selection hash to the enclosing alias receipt.
Extending that receipt changes the evidence hash for older aliases even when their
rows and selected prices are identical. Compare original alias rows and recompute
their receipt-bound hashes; do not mistake a provenance update for a price change.
The full comparison and remaining 6-1 scope are in the September 17 source-routing
review. Ordinary provider matching is still not publication admission.

### V7 reusable causal proposal build

`proposal_store.py` computes one feature/signal set per action epoch, stores
packed boolean signals and reuses bounded variant columns across epochs for
proposal simulation. Completed epochs and proposal batches resume only with
identical input/source/catalog/runtime bindings. JSON round-trips package tuples
as lists: compare canonical runtime identities, not raw container types. Preserve
raw execution prices separately from adjusted strategy-stop units. The AAPL
all-catalog build and unchanged-receipt resume are in the September16 review;
this is a component result, not full-universe or new option-risk admission.

### V7 compact proposal and stored-row consumption (September 17)

`StoredProposals` verifies and streams the typed Parquet format; do not expect
`proposals.jsonl` in new builds. Its declaration retains every variant, even if
no entry was eligible. Membership gates entry decisions only, not later exits.
`StoredFeatureRows` must use saved raw-unit moving averages: recomputing from an
action epoch's observed-only bars loses prior warmup, and reversing normalized
averages may change floating arithmetic. Bind retained daily/sector inputs and
verify the adapter's bindings at completion. Full context, demand and label
consumers remain separate. See the September17 compact-proposal review.

### V7 selected-contract feature demand (September 17)

`EntryDemand` consumes the compact proposals and retains every target identity
even when different targets select the same contract. Targets can have different
future roll paths; sharing tick requests is not permission to merge labels. Its
exports request only pre-decision quote/trade feature windows, including the
causal quote seed. They do not cover entry fills, minute marks, exits, rolls or
physical delivery. Extend and reconcile those scopes before scheduling capture.
Keep each contract/day in one exported capture batch to prevent overlapping
immutable shards across archives. Current store/CLI require early single-thread
configuration before Polars initialization.


### V7 pre-tax dividend ledger (September 17)

The separate user-authorized finite policy is
`docs/specs/V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`; its proposal remains an
immutable historical snapshot. `compile_v7_stock_cash.py` verifies original
provider references and the approved 4,337-event set, not every compiled cash
action. The 55 other events remain unresolved. Runtime uses cash entitlements
through `physical.cash_entitlements`. Ex/record/pay agreement does not establish
historical broker posting: release is the accepted first regular open strictly
after pay date, with zero modeled withholding/dividend fees.

Beneficial shares follow funded trade/exercise/sale decisions, not delayed
settlement entries. A pre-ex purchase can be entitled while unsettled; an ex-open
purchase cannot. Put delivery and pre-ex sale remove entitlement; a post-ex sale
does not remove the receivable. Receivables add equity without funding entries
or exercise, and remain until release even after the originating stock position
has closed. Reconciliation checks both accrual/release history and remaining
receivables. Runtime requires captured trading and settlement coverage through
release; compiler output alone does not admit held history.

`validate_v7_stock_cash.py` verifies the complete finite cash census and the
existing captured AAPL May 5, 2022 funded purchase. Its normalized 2022 settlement
calendar is based on the visually reviewed original FINRA annual notice and
46 checked table rows; it is not authorization to infer 2023–2026 calendars.
Keep the original failed OCC/DTCC requests and unresolved 2023 Veterans/2025
mourning distinctions. [Review](docs/reviews/2026-09-17-v7-stock-cash-ledger.md).
