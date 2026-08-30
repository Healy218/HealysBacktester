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

**Job `marks-build-38d8160-081935`** (fleet v3, launched 2026-08-30
13:19Z): 441 tasks, image `38d8160`, n2-highmem-8 SPOT, 5 packed
1.5-core/12GiB tasks per VM, 8h leash, **local-SSD scratch shared per VM**
(`/mnt/disks/ssd` host → `/mnt/ssd` container; task.sh stages ONE cache
copy per VM under flock at NVMe speed). Rows → `out/v5/meta_rows/`,
marks → `out/v5/meta_marks/`.
The sizing saga (each config was piloted or measured, all in submit.sh
comments): e2-standard-4 spot → preempted 3x/5h (n2 spot never preempts
here); 8-packed + pd-standard → page-cache overflow, I/O starvation, ONE
symbol in 11h; 5-packed + 70GB pd-balanced → healthy but ~1.4h/slot
staging tax (pd throughput scales with disk SIZE — small disks crawl);
local-SSD v3 → staging 85min→3min (MSFT pilot). Mount gotcha: COS root is
read-only — host mounts MUST be under /mnt/disks/, bind into the
container. When the fleet ends: assemble (`--membership` ON), then the
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
