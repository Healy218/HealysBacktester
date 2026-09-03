# HANDOFF — state for the next session

Written 2026-09-03 ~15:10 CDT. Protocol: `CLAUDE.md`.
Previous handoff: `handoff-history/HANDOFF-2026-09-01-v5-build-checkpointed.md`.

## The one-paragraph state

**v5 dataset build: 366/441 rows** (`gs://healys-backtester/out/v5/`,
matching `meta_marks/` count). Freeze is long done (453/453, merged spec at
`artifacts_v5_in/baseline_spec.json`, 441 frozen + 12 skipped-thin).
Three producers are running RIGHT NOW and coordinate only through the
bucket skip-check. **Credits are nearly gone — $36.85 of $300 remained on
2026-09-02 and a hard guard now caps this run at $32.** After the build:
assemble and training run **on the home box, not the cloud** (doctrine
reversed 2026-09-03 — see below). The live V118 scanner on `main` is
untouched by all of this.

## RUNNING RIGHT NOW — what to leave alone, what dies with the session

| What | Where | Survives a session clear? |
|---|---|---|
| Box build workers (3, symbols I*) | `scripts/run_build_v5_local.sh`, detached, `logs/build_v5_local.log` | **YES** (`setsid nohup`) |
| Budget guard, $32 cap | `scripts/cloud_budget_guard.sh`, detached, `logs/budget_guard2.log` | **YES** |
| Cloud fleet n2 `marks-build-4cca795-122502` | GCP Batch (20 running, 309 done, 2 failed) | **YES** |
| Cloud fleet c2d `marks-build-4cca795-122504` | GCP Batch (mostly skipping already-built) | **YES** |
| Server dead-man, hourly | systemd **user** timer, linger on | **YES** |
| StockTwits hourly collect+push | systemd user timer | **YES** |
| In-session Monitors (progress/stall watchdogs) | this CLI | **NO — re-arm early** |

Nothing here needs babysitting; the guard cancels the fleets on its own.

## Money — read before spending anything

- **$36.85 of $300 credits left** (console, 2026-09-02). The account is
  **PAID** since 2026-08-27, so credits hitting zero means the card gets
  charged. There is no native GCP spend cap.
- The guard is the only real brake: time-budgeted, detached, cancels the
  named jobs and pages Telegram. Currently **$26.54 spent of $32** with
  ~5.5 h of runway. Raising a budget mid-run requires `SPENT_USD=` or it
  silently grants a fresh full budget.
- Full mechanics + the post-mortem of how $263 went: **DOCUMENTATION.md →
  "GCP billing — how it actually works"**. The short version: burn rate x
  duration was never multiplied, and estimates came from solo-pilot
  economics rather than fleet economics.
- Remaining after this run (~$5) is enough for assemble + training ONLY
  because both now run on the box for free.

## When the build finishes (441/441, or when you decide to stop)

1. **Reconcile**: diff `out/v5/meta_rows/` against the spec's 441 symbols;
   3 tasks have died permanently to exhausted retries across the campaign.
   Rebuild stragglers on the box — it is free and faster per worker.
2. **Audit marks coverage** for symbols finished after 2026-09-01 00:33Z
   (the incomplete-checkpoint window, fixed in `4cca795`) — bounded to
   ~8 symbols plus whatever was in flight.
3. **Assemble on the box**, `--membership` ON (default for v5). Pull all
   row+marks shards down first (~1 GB; most exist only in the bucket).
   Watch memory on the mark stream — see TODO block 6 for why.
4. **Determinism check, then** the evaluate/finalize ladder on the box.
   Run evaluate twice with identical seeds and diff `SHA256SUMS.txt`;
   byte-identical means no silent bit flip. This gates trusting any
   box-trained bundle — it ships to production.
5. Verdict row in `docs/EXPERIMENTS.md`: does the wide pool beat v31?

## Doctrine change 2026-09-03 — training may run on the box

`task.sh` used to forbid it, citing PROVEN single-bit memory corruption.
That was **the i5-11400 with the faulty RAM, retired 2026-08-23** — the
premise died with the machine, so the rule did too. Full reasoning and
rejected alternatives in `docs/DECISIONS.md`; the comment in
`deploy/gcp/task.sh` is rewritten in place so nobody re-applies it. The
risk that survives: the new DDR5 is unvalidated, hence the determinism
check above. The box is also simply the better machine here — measured
2.33 symbols/hour vs 1.98 from a 4-VM spot fleet, ~5x per worker.

## Standing warnings

- **Never `pkill -f` a pattern that matches your own watcher.** Doing
  exactly that on 2026-09-03 killed the monitor and left the fleets
  briefly unguarded. Use the bracket trick: `pgrep -f '[c]loud_budget'`.
- Image `4cca795` is the current build image and carries the
  incomplete-checkpoint fix. `submit.sh` now refuses to submit against a
  tag with no manifest — never confirm an image from `gcloud builds list`.
- The 12 skipped-thin symbols are RESULTS; the build shards only the
  spec's 441.
- Cloud state is never re-derived from memory: `gcloud batch jobs list`
  plus `gsutil ls out/v5/meta_rows/` is the ground truth.
- Post-campaign cleanup still owed: stale Artifact Registry tags (a real
  cost item now, on a paid account). Keep `4cca795`.

## Next campaign, first item

TODO block 6 has the fully-measured universe read-path plan (derive
sorted → read filtered → scan the slice). Headline: `get_chain` scans all
5.2M rows per call at 216 ms when the symbol needs 21k rows and 0.70 ms —
**310x** — and each worker holds a redundant 0.96 GB copy. Prerequisite
nobody would guess: `derive_contracts` writes the parquet unsorted, so
predicate pushdown skips nothing until that changes.
