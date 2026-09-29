# Handoff — September 29, 2026 — V7 resumed after V6 configuration

## Focus and changes

User explicitly selected V7 resumption after the V6 worker configuration change,
without waiting for V6 catch-up/training. V7 gate 7-3 remains selected/open.
[Recovery evidence](docs/reviews/2026-09-29-v7-resumed-discovery-and-capture.md).

V7 planner completed all 591 securities: 793,394,264 original proposals and
328,386,847 distinct horizons. New recovery controller preserves unchanged wave
workers/contracts and partial ledgers. Aggregate storage now follows live free
space with a 10-GB floor and pending-write reserve. Both empty-index cases have
verified zero proposals/selections; original interrupted progress/journals recovered.

Frozen actual frontier: 109,825 missing quote windows plus 1,985 reference requests.
At 12:52 Central, quotes were 61,488 complete in 2,562 packs; 284 batch attempts
returned HTTP 502. Failures remain explicit. A retry service waits for the first
capture to stop, then reuses successes and retries missing batches up to three times.

All 1,985 dated references were captured/audited: 1,979 standard, six detail 404s.
Both alternate queries for each missing pair completed; two queries found matches.
Admission review remains required; no exclusions added. Twenty-one focused tests,
real empty-demand checks, snapshot validation and shell/Python checks passed.

## Active pointers and resource boundary

[CURRENT_STATE](docs/CURRENT_STATE.md#v7-full-universe-execution-discovery) owns
exact services and roots. Discovery controller: `v7-execution-recovery-20260929-r0`;
original waves remain in `v7-execution-campaign-20260928-r1/waves` (validation roots).
Capture controller: `v7-frontier-capture-20260929-r0`; raw quote output:
`nn_meta/data_v7/execution-recovery-20260929-r0`. Frozen snapshot:
`v7-recovery-frontier-20260929-r0`. Read the capture controller's `index-receipt.json`
for an actually sealed new index; do not infer availability from a target name.

Two discovery workers and four quote workers each have 5/6-GiB high/max, CPU 200%,
no swap. Stop new work at 15:00 Central and drain before V6's 15:45 timer; verify
actual exits. Retry waits consume no data workers. Dated observations are not
proof of current health. Discovery counts its current traversal; retained global
coverage must be reconciled across all per-wave receipts.

V6 worker increase remains installed: up to four autosized data workers,
CPU 400%, 19/20-GiB limits, two training threads. Original r3 config/root/snapshot
and all 74 source hashes preserved. Morning catch-up stopped at 93/449 symbols;
no new training/freeze. Calendar guards remain. [V6 change](docs/reviews/2026-09-29-v6-worker-sizing.md).

## Next actions

1. Observe V7 capture, discovery and retry receipts/exits; reconcile remaining
   HTTP-502 batches and actual disk use. Do not count failed attempts as coverage.
2. Review six unavailable held references and captured alternate matches. Preserve
   the approved 10,831 exclusions; additional exclusions require specific approval.
3. Bind completed quote/reference epochs, replay remaining paths and freeze/capture
   subsequent actual gaps. Full 7-3 closure still needs held/provider/storage census.
4. Observe the next allowed V6 autosized run; finish catch-up, 40 training members
   and evaluation. Candidate acceptance never deploys it.
5. Maintain first paper-fill observation, October 2 provider decision and FA schedules.

Preserve unrelated dirty work, source hashes, original entry packs and completed
gates 7-1/7-2. Keep execution/assembly/training milestones distinct.
