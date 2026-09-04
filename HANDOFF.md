# HANDOFF — state for the next session

Written 2026-09-04 ~04:00 UTC (2026-09-03 ~23:00 CDT). Protocol: `CLAUDE.md`.
Previous handoff: `handoff-history/HANDOFF-2026-09-03-v5-build-366-guard-and-box-workers-alive.md`.

## The one-paragraph state

**v5 dataset build: 393/441 rows and finishing in the cloud overnight,
unattended and unguarded — deliberately.** The home box is DOWN for
hardware repair (user, 2026-09-03 evening); its build workers and the
budget guard died with it. The user explicitly approved letting the two
GCP fleets drain on their own, accepting up to **~$20 on the card**
(credits were ~$5 at decision time; the account is paid). The fleets
self-terminate: verified via `gcloud batch jobs describe` that both carry
`maxRetryCount: 3` + `maxRunDuration: 8h` per task, so every task ends
and VMs deallocate when the queues drain. Expected residual cost ~$13.
The live V118 scanner on `main` is untouched.

## FIRST ACTIONS next session (in order)

1. **Ground truth on the overnight run** — never from memory:
   `gcloud batch jobs list --location=us-central1` and
   `gsutil ls gs://healys-backtester/out/v5/meta_rows/ | wc -l`.
   Expect both `marks-build-4cca795-122502` (n2) and `-122504` (c2d) in a
   terminal state and the row count near 441 (438 is the realistic max —
   3 tasks are permanently dead to exhausted retries; 2 of those FAILED
   tasks were already terminal on the n2 fleet at handoff time).
2. **Check what it actually cost** (console billing). Baseline: ~$5 of
   credits left at 2026-09-04 04:00 UTC, burn ~$1.00/hr for the 4 spot
   VMs. If jobs are still RUNNING well past ~17:00 UTC, something wedged —
   cancel them by name.
3. **Reconcile stragglers**: diff `out/v5/meta_rows/` against the 441
   symbols in `artifacts_v5_in/baseline_spec.json`; rebuild the gap on the
   box (free, ~5x faster per worker) once the box is trusted again.
4. **The box returns from a hardware repair — validate before trusting.**
   Run memtest86+ while reboots are cheap (it gates everything below),
   then the determinism check (evaluate twice, identical seeds, diff
   `SHA256SUMS.txt`) before trusting any box-built artifact. This was
   already doctrine for the unvalidated DDR5; a repair visit makes it
   mandatory, not optional.
5. Then the standing ladder from TODO block 6: audit marks coverage for
   post-2026-09-01-00:33Z symbols (~8 + in-flight) → assemble on the box
   (`--membership` ON, pull ~1 GB of shards down first, watch the mark
   stream memory) → evaluate/finalize → verdict row in
   `docs/EXPERIMENTS.md`.

## What died with the box (do NOT assume these are running)

| What | Status at handoff |
|---|---|
| Box build workers (`run_build_v5_local.sh`) | **DEAD** — last log 2026-09-03 16:21 CDT; user confirmed not running |
| Budget guard (`cloud_budget_guard.sh`) | **DEAD** — last log 21:21Z; fleets ran unguarded ~6.5h before the user noticed; spend blew past the $32 cap the guard would have enforced (est ~$34 when checked) |
| In-session Monitors | gone with the session |
| Server dead-man + StockTwits timers | systemd user timers on the box — **also down while the box is down**; the Hetzner server itself is independent and stays up |

The server dead-man being down means server incidents page nobody until
the box is back. Worth knowing, not worth panicking over.

## Money

- Credits effectively exhausted: ~$5 left when the overnight decision was
  made; overnight drain lands the overage (~$3–9, ceiling ~$15 absent a
  pathological straggler) **on the card, with the user's explicit OK
  (2026-09-03 evening, cap ~$20)**. Do not re-litigate; do not extend.
- The guard's lesson stands: it is the only brake, and it lives on the
  box. Any future cloud spend while the box is down runs uncapped.
- Post-campaign cleanup still owed: stale Artifact Registry tags (real
  cost on a paid account). Keep `4cca795`.

## Standing warnings (carried forward)

- **Never `pkill -f` a pattern that matches your own watcher** — bracket
  trick: `pgrep -f '[c]loud_budget'`.
- Image `4cca795` is current; `submit.sh` refuses tags with no manifest.
- The 12 skipped-thin symbols are RESULTS; the spec's 441 is the universe.
- Freeze is DONE (453/453, spec at `artifacts_v5_in/baseline_spec.json`).
- Doctrine 2026-09-03: assemble + training run **on the box** (DECISIONS);
  the determinism check is the gate, doubly so after the hardware repair.

## Next campaign, first item

Unchanged: TODO block 6's universe read-path plan (derive sorted → read
filtered → scan the slice; 310x measured on `get_chain`). Prerequisite:
`derive_contracts` writes the parquet unsorted, so predicate pushdown
skips nothing until that changes.
