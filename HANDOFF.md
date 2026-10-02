# Handoff — October 2, 2026 — larger V7 discovery pool

## User direction and deployment

User requested maximum supported discovery workers and an ETA from actual work.
Corrected resource policy v4 resumed at **13:39:30 Central**, retaining all
optimized campaign/wave contracts. Nine workers were observed at 13:40.
[Policy and evidence](docs/reviews/2026-10-02-v7-discovery-concurrency.md).

Selected service is still `healys-v7-required-discovery-20260930.service`.
Runtime `zzzz-resources-v4.conf` selects `finish_v7_discovery_resources_v4.py`,
which uses scheduling controller `run_v7_optimized_campaign_v3.py`.
The original scientific discovery wave v4 is unchanged. Replay retains its
existing supervisor and one-worker policy. No model or paper-policy deployment.

## Admission correction

The installed supervisor gives research workers `OMP_NUM_THREADS=1`. GNU nproc
also honors that variable, so the shared autosizer was capping the whole pool
at one. The corrected policy clears OMP_NUM_THREADS/OMP_THREAD_LIMIT only for
sizing. Numerical workers remain single-threaded. It also accounts for already
resident worker memory when computing total pool capacity.

Up to twelve workers, bounded by CPU threads minus two and memory. Allowance
starts at 1 GiB and grows with observed anonymous/kernel working sets. Preserve
4-GiB host headroom, unconsumed 12-GiB paper allowance, 20-GiB incubation allowance
before/through its afternoon window or while active, and 1-GiB replay allowance.
Service remains 12/14-GiB high/max, no swap, no CPU quota. Five-minute slices drain
normally when admission drops. Read actual active/admitted counts; old two/four
ceilings are historical. The intermediate r3 deployment retained the nproc cap;
its mixed measurement is superseded and must not be used as multiworker evidence.

## Selected state and evidence

Campaign: `nn_meta/validation/v7-required-inputs-20261002-perf-r0/`.
Discovery still uses `discovery-campaign/`; replay `epochs/00001/replay/`.
One wave link per security preserves cumulative counts without double counting.
New scheduler binding: `discovery-campaign/resource-revision-v3.json`.
Watcher pointer remains `logs/lab-hourly-watch/v7-selection.json`.

Resource evidence: `nn_meta/validation/v7-discovery-resources-20261002-r4/`:
`before.json`, `stopped.json`, `deployment.json`, `measurement.json`,
`measurement-summary.json`. 29 focused tests passed, including the inherited
thread environment and preserving existing declarations. Gate 7-3 remains open.

## Measured result

13:39:30–13:54:30 Central: +25,520 groups / +2,362,080 assessments,
9.45 million/hour with 7–9 workers. Remaining original discovery projects to
6.59 continuous days at that short-window rate; capture/replay and incubation
pauses are additional. Paper was provider-blocked, so full co-load is unproven.

## Operating checks

Hourly watcher continues here. V6 paper separately hit Massive HTTP 403 at 13:30
in bar refresh and held monitoring, before the larger pool started. Observe
subsequent scanner receipts; broker polling success does not resolve that error.
Do not change trading state in the watcher. Successful idle incubator/storage
completion remains omitted. Preserve all checkpoints and unrelated dirty work.

User cancelled Massive options today and requested removing its V6 dependency.
Alpaca live OPRA quotes work; historical quote REST probe returned 404. A versioned
live-quote adapter is being tested; feature-path choice remains pending. No model
or feature deletion is admitted by this concurrency milestone.
