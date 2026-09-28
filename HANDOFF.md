# Handoff — September 28, 2026 — entry download complete; V6 catching up

## Stopping point

**7-3.entry is complete. Overall gate 7-3 remains open.** V7's selected entry
capture completed successfully at 04:58:11 Central. V6's completion-gated timer
then started its catch-up automatically at 05:00:27. At the 06:17 observation,
V6 was still building data, with four of 449 symbols complete and no training.
The initial catch-up will not produce a new model for this trading morning.
[Evidence](docs/reviews/2026-09-28-overnight-entry-completion.md).

## Verified results

- V7: full entry coverage, zero pending work, no stop reason, successful service
  exit. Final campaign count 10,940,386 exactly reconciles with 10,941,828 original
  joined ranges minus a net 1,442 removed by prior indexed capture coverage.
- The final receipt recorded 144.35 GB retained campaign files. Capture artifacts,
  source-bound producers and all existing preparation remain frozen.
- V6: automatic wait/restart worked. Four completed symbols contain 3,364 candidates:
  2,042 matured, 707 pending and 615 unfilled. Other partial progress is checkpointed.
  No candidate/accepted-model pointer exists. Full-universe build latency remains
  unproven despite the successful single-member training benchmark.
- Morning retries start at midnight Central, every 15 minutes through 07:45.
  The existing 08:00 cutoff and old operational model remain in force.

## Next actions

1. Read TODO, then inspect current V6 status, per-symbol progress and service log
   via [CURRENT_STATE](docs/CURRENT_STATE.md). Main status advances on completed
   symbols; it is not a frequent heartbeat. Do not infer a job is healthy from
   this handoff's dated snapshot.
2. Continue the existing 7-3 references/actual held-path gaps and reconciliation.
   Do not repeat entry capture, catalog, daily build, demand census or packing.
   Retain the selected partial 7-4 ledger and version any source changes.
3. Finish V6 initial catch-up, full ensemble freeze and one measured daily update.
   Its actual full-universe data build is the bottleneck to investigate; the
   isolated 191-second member benchmark does not imply overnight readiness.
4. Observe Monday's prospective Alpaca fills separately. Keep the October 2
   provider decision. V6 data producer succeeded at 06:00; this does not establish
   broker fills, model quality or readiness.

## Constraints

V6 incumbent/parent freezes and broker state stay isolated from research. New
source/config needs a new research lineage; do not relabel old checkpoints.
Full-scope validation, deployment and measured outcomes remain separate.
The diagnostic validation tail overlaps original incumbent training dates and
is not an untouched performance test. Preserve unrelated dirty/untracked work.
