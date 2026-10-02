# V7 optimized controller adoption — October 2, 2026

The user authorized integration, checkpoint verification and resumption after the
bounded performance comparison. Both selected services resumed at **12:45:08
Central**, using the new source-bound supervisor and campaign controller. Gate
7-3 remains open; this adoption does not complete input coverage or deploy a model.

## Selected artifacts and preservation

New root: `nn_meta/validation/v7-required-inputs-20261002-perf-r0/`.
`discovery-campaign/` owns the original 591-security continuation;
`epochs/00001/replay/` continues the retained 93-security replay. The supervisor
continues subsequent actual-demand capture/reference/replay epochs and eventually
the full original-discovery frontier. Completed initial replay and epoch-00001
capture are reused from their existing verified locations.

Each campaign has a new declaration/configuration. `waves/<security>` selects
exactly one retained predecessor or optimized successor. Completed predecessors
stay selected. Unfinished waves import into `revisions/<security>` and switch
atomically after publishing durable progress. Import records original declaration,
binding and physical database hashes; no old binding is relabeled. Reporting
reads this selected view, never sums the predecessor and successor. The watcher
selection is `logs/lab-hourly-watch/v7-selection.json`; service names are unchanged.

The unfinished discovery and replay databases total about **80.93 GB logical**;
local free space before adoption was about **94.3 GB**. Ordinary duplication would
breach the working reserve. Imports require filesystem copy-on-write clones with
independent inodes, verify source/destination hashes and SQLite integrity, and
recover only the new copy. A staged import can resume after interrupted directory
publication. An unsupported clone fails explicitly rather than silently copying.
Original data and benchmark evidence remain preserved. Local working controllers
retain a **20 GB reserve plus 512 MiB per admitted write slot**. This is headroom
for continuing work, not evidence that all remaining output will fit. Existing
sealed capture overflow routing remains unchanged.

## Validation and resources

- 35 focused tests passed: imports, interrupted publication, scientific-input
  rejection, atomic progress selection, existing exact persistence/quote behavior,
  resource admission, frontier contracts and hourly reporting.
- Two real discovery checkpoints advanced 40 cohorts each through the integrated
  controller; one retained replay advanced 40 cohorts. Independent unchanged
  baseline producers matched all six scientific tables exactly. Original physical
  checkpoint hashes stayed unchanged; copied database inodes are independent.
- Discovery canary retained cumulative totals: **1,534,576 cohorts / 143,956,370
  assessments**, 67 terminal securities including seven empty cases, 133 partial.
  Replay: **172,823 cohorts / 14,525,409 of 20,015,688 assessments**, 47/93 finished.
  These include pending-input outcomes and do not imply completed labels.
- Dynamic discovery admission remains at most **two weekdays 07:00–21:00 Central,
  four otherwise**, with a conservative 3-GiB worker allowance and 18/12-GiB
  host/V6 reserves. Replay remains one worker. Zero new admissions can coexist
  with active slices and is a resource wait, not lost progress.
- Discovery service remains 12-GiB high / 14-GiB maximum; frontier 5/6 GiB, no
  CPU quota and no swap. Bounded slices run up to ten minutes. Stop drains them;
  service stop timeout is now 30 minutes rather than killing an import early.

The scientific optimization is unchanged from the
[bounded benchmark](2026-10-02-v7-performance-benchmark.md): discovery 1.59× and
replay 1.22× on matched samples. This adoption does not turn those results into a
whole-universe ETA or establish full-scope memory maxima.

## Evidence and operation

Under the new root: `adoption.json`, `deployment-before.json`, `deployment.json`,
`canary-validation/{complete,parity}.json`, campaign declarations and inherited
checkpoint receipts. `verification.json` records subsequent observed progress and
paper coexistence. Exact launchers: `finish_v7_optimized_inputs_v1.py`,
`run_v7_optimized_campaign_v1.py`, discovery wave v4 and replay wave v3.
The wave revisions add staged copy-on-write inheritance to the validated producers.

The two runtime drop-ins are `zz-optimized-v1.conf` under the existing
`healys-v7-required-{discovery,frontier}-20260930.service.d` directories.
`install_v7_optimized_adoption_v1.py` requires successful parity evidence and stopped
predecessors before installing and starting them. No paper service, model or order
policy is changed by this deployment.
