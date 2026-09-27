# Handoff — September 27, 2026 — eight-worker download selected

## Focus and stopping point

The user authorized increasing the entry download to 192 concurrent requests,
then trying 256 if measured throughput improved. Both trials are complete.
The v6 capture service is running with **8 workers × 32 I/O threads**, a ceiling
of 256 concurrent requests. Research remains in Phase 7, gate 7-3.

## Changes and evidence

- New versioned runner/launcher and policy; all prior source-bound producers,
  completed packs, data scope, memory guard and storage routing are preserved.
- Six workers reused all 27,894 prior packs; eight reused all 28,891 packs after
  the six-worker trial. Both transitions drained with no pending writes/reservations.
- Live samples support eight workers; no errors, retries, provider throttling,
  CPU-quota throttling or memory-limit events in the observation windows.
  [Review and measured rates](docs/reviews/2026-09-27-v7-eight-worker-capture.md).
- 14 GiB RAM, no swap, 800% CPU quota, low priority and 10 GB reserves on both
  local/MRHA storage remain. TasksMax now accommodates 256 I/O threads.
- 24 focused tests passed; full suite: 2,514 passed, 1 skipped, 18 subtests passed.
- Documentation consolidation from the prior handoff remains complete. Canonical
  file ownership and the consolidated roadmap/TODO are unchanged.

## Next session

1. Read TODO, then [CURRENT_STATE](docs/CURRENT_STATE.md) for exact current pointers.
2. Inspect the v6 campaign progress receipt when asked for status. Do not start a
   duplicate or choose the historical v5 service/launcher. Short-window throughput
   varies with data density and is not a dependable whole-campaign ETA.
3. Continue selected 7-3 work using existing preparation; preserve the selected
   partial 7-4 ledger. No gate, assembly or training readiness was advanced here.
4. Observe Monday's first prospective Alpaca fills; preserve the activated account.
   Incubator source/outcome work and the October 2 provider decision remain the
   separate obligations in TODO. FA collection continues on its existing schedule.

## Constraints

Current source-bound v6 files are frozen too. Resume with the current runner;
older v5 cannot admit newly generated v6 packs. All completed data stays reusable.
Broad unrelated dirty/untracked implementation work remains; do not revert or
stage it wholesale. Runtime measurements are dated observations, not permanent
health claims. The 14 GiB guard may lower actual concurrency on denser ranges.
