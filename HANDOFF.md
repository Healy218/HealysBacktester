# Handoff — October 2, 2026 — optimized V7 adopted and resumed

## User direction and result

User authorized finishing integration/checkpoint verification and resuming V7.
Both selected services resumed at **12:45:08 Central**. This supersedes the 09:59
pause. Gate 7-3 remains open; continue actual discovery/frontier work and observe
resource waits/errors. No paper/live model promotion.
[Adoption review](docs/reviews/2026-10-02-v7-performance-adoption.md).

## Selected continuation

State: `nn_meta/validation/v7-required-inputs-20261002-perf-r0/`.
- `discovery-campaign/`: original 591-security scope, new source-bound declaration.
- `epochs/00001/replay/`: retained subset, same frozen 20,015,688-target denominator.
- `discovery/progress.json`, `frontier/progress.json`: supervisors and errors.
- `adoption.json`, `deployment.json`, `verification.json`: configuration/observations.
- `canary-validation/{complete,parity}.json`: exact real-checkpoint comparisons.

Services retain names `healys-v7-required-{discovery,frontier}-20260930.service`.
Runtime `zz-optimized-v1.conf` selects `finish_v7_optimized_inputs_v1.py` and
`run_v7_optimized_campaign_v1.py`; wave consumers are discovery v4/replay v3.
Old controllers, declarations, original checkpoints and completed captures remain
preserved. One atomic wave link per security selects its retained predecessor or
new revision. Reporting never adds both as unique work. Watcher selection:
`logs/lab-hourly-watch/v7-selection.json`. Hourly checks remain active here.

## Verification and limits

35 focused tests passed. Two discovery canaries (+40 cohorts each) and one replay
(+40) matched unchanged baseline producers across all six scientific tables.
Original physical checkpoint hashes stayed unchanged. Inheritance requires
copy-on-write clones with independent inodes; interrupted publication is resumable.
The ~80.93-GB unfinished logical checkpoint set is not immediately duplicated.
Controllers reserve 20 GB local free space plus per-worker write headroom.

At 12:48: discovery had 1,534,664 cohorts / 143,967,810 assessments; 67 terminal
securities including seven empty, 133 partial. Replay had 174,088 cohorts /
14,659,618 assessments and **48/93 finished**, up from 47. Both services running,
no errors. One discovery worker active; new admissions waited for memory while
V6 scanned. Read fresh receipts; these are dated observations, not live health.

Discovery admission remains at most two daytime/four overnight, 3-GiB allowance,
18/12-GiB reserves; one replay worker. Services retain 14/6-GiB maxima and no CPU
quota. Slices run up to ten minutes; stops drain with a 30-minute service timeout.
The earlier bounded speedups (1.59× discovery/1.22× replay) are not full-scope ETAs.

## V6 and next checks

V6 paper retains the ten-minute signal-close entry window installed at 10:36.
Models, 30-second quote freshness and order ladder remain unchanged. Observe
scanner completions separately from broker polling/fills. V6 daily incubation
schedules remain independent. Hourly reporting omits successful idle incubation
and completed storage. Inspect new V7 progression, resource waits and downstream
epoch transitions; preserve all checkpoints and unrelated dirty/untracked work.
