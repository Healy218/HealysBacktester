# DOCUMENTATION — coding notes, conventions, traps, ops

Durable reference for anyone (human or model) working in this repo. Goals
live in `ROADMAP.md`, current tasks in `TODO.md`, session state in
`HANDOFF.md` — this file is for how things *work*.

## Environment

- **Repo**: `/home/healylabs/Coding/HealysBacktester`, working branch
  `codex/v4-causal-validation`; `main` is the operational line the server runs.
- **Python**: `./venv/bin/python` (3.12.3). No conda, no system python —
  always call the venv binary explicitly.
- **Tests**: `./venv/bin/python -m pytest tests/ -q` — 345 tests, green.
  They must stay self-contained: no LightGBM, no network, no v31 artifacts.
- **Secrets**: `.env` at repo root, never in git. Keys: `ALPACA_API_*`,
  `MASSIVE_API_KEY`, `MASSIVE_FLAT_FILES_API_*`, `ALPHAVANTAGE_KEY`,
  `FINNHUB_API_KEY`, `REDDIT_CLIENT_*`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `FA_SKIP_COLLECTORS`.
- **`NN_META_POOL`** selects the strategy pool AND suffixes every artifact
  dir (`nn_meta/config.py`): v2 (default) / v3 (live scanner) / v31 (at-scale
  + v4 work). Setting it wrong silently reads and writes the wrong
  directories — the most common way to burn an evening.
- **Home box** (rebuilt 2026-08-23): Ryzen 7 9850X3D (8C/16T + iGPU),
  32 GB DDR5, RTX 3060 Ti, 1 TB NVMe, CachyOS, user `healy`. The old
  i5-11400/B560 build (proven RAM fault — hourly `fa.collect` segfaults on
  its final morning) is retired; the drive moved over intact, so the OS
  install and all paths are unchanged. TF is CPU-only here in practice; the
  heavy work is memory-bound dataset builds, not training — which still run
  on GCP Batch by doctrine, not here.

## Conventions

- Small, single-purpose, specifically-messaged commits. Commit and push
  often — don't leave hours of work sitting uncommitted.
- **Scripts derive their own repo root**:
  `cd "$(dirname "$(readlink -f "$0")")/.."`. Never reintroduce an absolute
  local path — that's what broke every launcher when the WSL2 box was retired.
- **Never hardcode worker/shard counts.** Source `scripts/lib/autosize.sh`
  and call `autosize_workers <per_worker_mb>`; it divides MemAvailable (less
  a 2 GB reserve) by the budget and caps at `nproc`. Build/freeze workers
  hold ~2.1–2.7 GB RSS each; with the desktop up the right answer is ~4
  shards, headless ~5.
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
- Run logs write to the **repo root**, not `logs/` — `.gitignore` covers
  them with an anchored `/*.log`.
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
  persisted in `ev` mode fails to LOAD if any member lacks its head. Bundles
  from before 2026-08-21 have no magnitude files and still load.

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

- **The agent Bash tool's shell is `zsh`, not bash — unquoted `$VAR` does NOT
  word-split.** Building a flag string and expanding it unquoted silently
  passes the whole string as ONE argument. This produced two false
  `UNREACHABLE` readings in a Batch watcher on 2026-08-20:

      P="--project=healys-batch --location=us-central1"
      gcloud batch jobs describe "$J" $P ...
      # ERROR: The project property must be set to a valid project ID, not the
      #        project name [healys-batch --location=us-central1]

  Inline the flags, or use an array. Note the same call worked fine when typed
  directly, so it reads as a flaky API rather than a quoting bug — check for a
  variable-expanded flag string before blaming the service. (`gcloud storage`
  kept working throughout, because it had no variable to split.)
- **A multi-step `sudo a && sudo b && sudo c` chain runs only the FIRST
  command** on this box; the sudo journal proves it each time. Wrap privileged
  multi-step work in a single `sudo bash -c "..."`. Separately, the `!` prefix
  in the CLI runs bash, not the user's fish, so `; and` chaining fails there.
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
- `nn_meta/model_final_v4/` (Option A bundle): `verify_bundle()` fails **by
  design** — the manifest predates hashed persistence (built 7/21, hashing
  landed 7/22). Usable, not integrity-verifiable; the Option B re-finalize
  fixes it.
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
- **The crawl's CURRENT-year end date must stay at today-00:00.** Asking for
  tomorrow returns `subscription does not permit querying recent SIP data` and
  fails the entire year, wiping that year's fetch. Yesterday's close is the
  most this Alpaca tier holds; the current year is refreshed every run anyway.
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

## Artifact map — what's where, and what's deliberately not in git

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
  which is the brake GCP does not provide (time-based auto-cancel).
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
- **Arm `scripts/cloud_budget_guard.sh` with every fleet launch.** It is
  the only hard stop that exists.
- **Re-derive spend daily** from `gcloud batch jobs list` durations x VM
  count x rate. Do not wait for the console.
- **The home box is free and fast.** Measured 2026-09-02: 2.26 symbols/hour
  on the Ryzen (3–5 autosized workers) — roughly half the 4-VM cloud fleet's
  output, at zero cost. For embarrassingly-parallel work, run the box first
  and treat cloud as the accelerator you pay for, not the default.
- **Deleting stale Artifact Registry images is now a cost item**, not
  housekeeping: ~12 TF-heavy tags at ~$0.10/GB/month.

## Data limits (probed, definitive — don't re-litigate)

- **Massive options history reaches ~2 years back** (403 before ~mid-2024),
  on REST *and* flat-files — the S3 bucket lists 2014→ but GetObject is
  date-gated. Deeper options history requires a **paid plan upgrade**, full
  stop. Contract listings (reference endpoint) reach 2017 fine.
- **Flat-files are still the right bulk path within the 2y window**: one
  ~33 MB gz/day covers all OPRA contracts, quota-free
  (`files.massive.com`, bucket `flatfiles`,
  `us_options_opra/minute_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz`, s3v4).
- **Alpaca 1m underlying is clean back to 2017** for all liquidity tiers.
- Consequence: features may use deep underlying history; option-fill labels
  live on the rolling ~2y window.

## Scale lessons (paid for; don't rediscover)

- The v31 **mark stream is ~88M rows** (489k trades × ~180 bars held).
  Assembling it via `pd.concat` peaks ~9 GB and dies on this box; the
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
- **Build workers are RAM-bound, not CPU-bound** — 5.4 GB RSS each against
  16 threads, so the box runs 3-5 workers with most cores idle. ~1 GB of
  each worker is a REDUNDANT copy of the 44 MB contract universe
  (`HybridProvider._get_universe` reads the parquet per process and then
  `.copy()`s it to normalize, spiking peak RSS 2.53 -> 3.17 GB). Sharing
  it (in-place normalize + pyarrow memory-map) buys a whole extra worker
  for $0 — see TODO block 6, first item of the next campaign.
- True dataset-build pace is ~33 min/symbol/shard on big names; don't trust
  burst extrapolations. **A v5 symbol is ~8h packed** (10 families × DTE
  grid vs v31's 5) — size leashes and stall alarms against that, not v31's.

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
  filled instantly. Run a **twin fleet on two families** — the global CPU
  quota caps concurrency anyway, so the second job is free insurance.
- **Never confirm an image from `gcloud builds list`** (the list-and-pick
  trap again). A silent Dockerfile-copy failure plus a stale list entry
  launched 441 tasks against a nonexistent tag — 148 instant failures on
  `manifest unknown`. `submit.sh` now gates on
  `artifacts docker images describe <IMAGE>` and refuses to submit.

## Production ops — Hetzner server

- **Host**: Hetzner CX33 (4 vCPU / 8 GB), Helsinki, `62.238.20.66`,
  Ubuntu 24.04, ~$9.59/mo. SSH `mrhea@` with the home box's
  `~/.ssh/id_ed25519` (that key is Hetzner-only; GitHub auth is `gh` over
  HTTPS). Repo at `/home/mrhea/HealysBacktester`.
- **Deploy = `git pull origin main` over the read-only deploy key. NEVER
  scp** — an untracked scp'd file once wedged pulls for days, silently.
- **Cron (UTC — this cron ignores `CRON_TZ`, verified empirically)**:
  - `*/15 * * * *` live scanner: `NN_META_POOL=v3 … run_live --once --nn`
    → `logs/live_cron.log` (self-gates to RTH)
  - `*/15 * * * *` **[v4] expert** (paper 2026-08-16 → **REAL 2026-08-24**,
    V118 bundle gbt/ev/0.05): `NN_META_POOL=v31 … nn_meta.live.v4_scan
    --once` → `logs/v4_cron.log`. The scan refuses to alert unless the
    bundle verifies AND is gate-eligible. **Rollback = restore
    `~/crontab.bak.2026-08-24`** (or re-add `--paper` / delete the line) —
    v3 is untouched. Needs `nn_meta/data_cache_v3/{surface_daily,
    underlying_daily}.parquet` on the host (rsync'd; gitignored path,
    refresh occasionally).
  - `*/15 * * * *` **[v31] expert** (since 2026-08-16): `NN_META_POOL=v31 …
    nn_meta.live.run_live --once --nn` → `logs/v31_cron.log`. Legacy scorer
    path (prices the frozen-DTE contract live via the hybrid provider);
    `[v31]`-labeled alerts; own dedupe file `.alert_state_v31.json`.
    Rollback = delete the line.
  - `0 10 * * 0` + `30 10 * * 0` **weekly universe refresh** (since
    2026-08-16): `download_universe --universe-only --live-horizon 120` for
    the v3 pool then the v31 pool → `logs/universe_refresh_*.log`.
    **Keep each pool's bars+surface steps `&&`-chained in ONE cron entry** —
    splitting them into separate times invites the refresh/compaction swap
    racing the surface build's glob-then-open. This is
    what keeps the live chain's expiries ahead of the calendar — the frozen
    research window does NOT roll forward on its own, and the chain
    silently empties ~45 days after the last refresh without it.
  - `10 20 * * 1-5` **[v4] watchlist digest** (since 2026-08-24, ROADMAP
    wave-2 item 5): `NN_META_POOL=v31 … v4_scan --digest` → one Telegram
    top-10 of the day's scored signals regardless of threshold, plus the
    rolling 7-day underlying-direction hit-rate (watchlist vs alerted
    subset). No model load; state `nn_meta/live/.v4_watchlist.json`
    (gitignored), 21-day retention. Rollback = delete the line.
  - `5 * * * *` FA collectors (`fa.collect`) → `logs/fa_cron.log`
  - `30 12 * * 1-5` trending digest (8:30 ET summer) → Telegram
  - `0 17 * * *` scanner heartbeat (noon CT summer): one line per expert
    (v3/v4/v31) — passes/alerts + NEW crashes per cron log since the last
    heartbeat, plus missing/stale-log warnings during RTH — silence = quiet
    market, not "is it dead?". Baselines in the gitignored
    `nn_meta/live/.heartbeat_state.json` (old single-log schema migrates in
    place; first heartbeat per log prints "baseline set").
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
- **v3 rollback**: drop `NN_META_POOL=v3` from the cron line (v2 artifacts
  still present, untouched). The once-documented `_st.py` selftest script
  no longer exists on the server (verified 2026-08-24) — check v3 health
  from `logs/live_cron.log` (a clean pass every 15 min) instead.
- State on the server that is NOT in git: `.env`, `fa/archive/`, the 5 root
  parquets of `nn_meta/data_cache/` (scanner needs `surface_daily.parquet`).

## Home-box scheduling (systemd)

- Installed + working: `healys-stocktwits.timer` (hourly, `Persistent=true`
  so missed hours catch up after downtime).
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
