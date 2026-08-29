# HANDOFF — state for the next session

Written 2026-08-29 ~04:45 CDT. Protocol: `CLAUDE.md`.
Previous handoff (the freeze campaign in flight):
`handoff-history/HANDOFF-2026-08-26-v5-freeze-campaign.md`.

## The one-paragraph state

**The v5 FREEZE IS DONE AND MERGED.** Fleet `v5-freeze-0f132b6-013536`
SUCCEEDED 2026-08-29 09:11Z: 453/453 per-symbol specs, zero failures,
zero preemptions, ~75h wall, ~$40. `freeze-merge` published the pool spec
to `gs://healys-backtester/artifacts_v5_in/baseline_spec.json` (10.3 MB):
**441 symbols frozen, 12 skipped-thin** (BKNG, DRAM, KLAC, leveraged
micro-ETFs…), and every one of the 10 families is some symbol's
best_strategy (rsi 182, stoch 49, bbands 46, volume 42, squeeze 40,
supertrend 39, ma 28, elliott 11, macd 3, tv_rating 1) — the wide pool is
genuinely diverse raw material. Next stage: the DATASET BUILD fleet.
A fresh image was building at `7833952` (Cloud Build, launched ~04:15
CDT) — that tag carries the task.sh pool-path fix the build stage
REQUIRES (`f4e787a`); the freeze image `0f132b6` must NOT be used for
build/assemble/evaluate (it would read/write v31's `out/` paths).

## Build stage: FLEET IN FLIGHT (launched 2026-08-29 17:45Z)

**Job `marks-build-7833952-124534`**: 441 tasks (one per spec symbol),
image `7833952`, n2-highmem-8 SPOT / 1-core 12GiB tasks / 8h leash /
pd-standard 100GB boot / PARALLEL=60. Rows land in `out/v5/meta_rows/`,
marks in `out/v5/meta_marks/`; ETA ~2 days at 32 CPUs.
History: pilot 1 on the old default e2-standard-4 spot was PREEMPTED 3x
in 5h and died (exit 50001, nothing published — a ~3h AAPL build can't
survive churny spot with only end-of-symbol checkpoints); pilot 2 on the
freeze shape SUCCEEDED (AAPL 3.6h, v5 paths verified live, v31's 118 row
files untouched). submit.sh now hard-codes this shape for non-v31 builds.
When the fleet ends: assemble (`--membership` ON), then the
evaluate/finalize ladder.

## Quotas / budget (verified live through 2026-08-29)

- `CPUS_ALL_REGIONS=32` still binding. The user's 64-CPU request
  (submitted 2026-08-28 on the now-UPGRADED paid account; prior request
  #74792265 was cancelled) is pending — if granted, fleets widen
  automatically (freeze sizing packs 5 tasks/VM; PARALLEL is set high).
- Regional SSD quota 500GB was the hidden width cap (4×100GB boot disks
  = 400/500) — freeze-mode boot disks now default `pd-standard`
  (`BOOT_TYPE` knob, commit `7833952`) drawing on the ~empty 4TB
  standard-disk quota.
- Credits: ~$162 of $300 remained per console 2026-08-28 (the $138
  consumed = whole project to date). Build+assemble+training projected
  $50–90. Console Billing → Credits is the balance page now (paid
  accounts lose the trial banner).

## This week's other events (all resolved, all committed)

- **Hetzner outage 2026-08-27 13:32Z → 08-28 ~20:20Z**: billing lapse
  null-routed the server IP while the box kept running; scanners failed
  closed (zero stale alerts), ~1.7 trading days dark. Recovered; runbook
  updated. **Reverse dead-man now live on the home box** (user systemd
  timer + linger, hourly SSH probe, Telegram page after 2 misses).
- Per-boot Telegram heartbeat from `boot_restart.sh` now defaults OFF
  (user decision — stable Ryzen box); relaunch notices still send. Its
  broken root-owned log rerouted to `boot_restart.d.log`.
- Post-campaign cleanup note stands: delete stale Artifact Registry tags
  when the campaign ends (keep the live one + current build tag).

## Standing warnings

- Freeze image `0f132b6` is for freeze/freeze-merge ONLY (pre-pool-path
  task.sh). Build stage: `7833952` or later.
- The 12 skipped-thin symbols are RESULTS, not failures — build only
  shards `spec["symbols"]` (441), so they're naturally excluded.
- Local monitors die with session restarts (seen repeatedly) — re-derive
  cloud state from `gcloud batch jobs list` + bucket paths, never from
  memory.
