# V7 discovery resource revision — October 2, 2026

The user asked whether discovery could use more workers. The deployed recovery
controller had a hard maximum of two, separately from the autosizer. Its CPU
quota was already unlimited. October 1 22:51:24–22:51:44 Central sampling measured
37.985 CPU-seconds over 20 seconds (about 1.9 cores); no CPU throttling or OOM.
Discovery memory included about 6.3 GiB of file cache and 0.6 GiB of anonymous
memory in the preceding sample. Host MemAvailable was about 24.7 GiB. I/O waits
were present but that short sample does not establish a permanent bottleneck.

## Implemented and deployed

New versioned scheduler preserves the original scientific wave producer, inputs,
wave declarations, SQLite checkpoints and original recovery declaration. It binds
its own sources in separate revision anchors; the mutable progress path remains
compatible with the existing frontier/watcher. Empty-demand receipts retain their
original campaign identity. No source hash checks were disabled or rewritten.

Admission uses the shared autosizer with 3072 MiB per prospective worker:

- Overnight: maximum four, 12288 MiB host available-memory reserve.
- Weekdays 07:00–21:00 America/Chicago: maximum two, reserve 18432 MiB for paper
  scanning and normal daily V6. This includes a lead-in before paper starts.
- Insufficient capacity: zero new admissions. Existing slices finish normally.
- Service MemoryHigh 12 GiB, MemoryMax 14 GiB, swap zero, CPU quota unlimited.

These are conservative admission estimates, not a measured per-worker peak or a
promise that four workers always fit. No change to the five-minute wave slice,
six-hour checkpoint passes, scientific output or unchanged single-thread workers.

Installer preflight verified predecessor/supervisor bound inputs. At October 2
08:00:11 Central the old controller had stopped cleanly at a checkpoint with no
errors; the new service started. All 195 prior wave declarations matched before
and after. At 08:00:55 two workers were active under the daytime policy, reporting
fresh progress, no failed securities or cgroup OOM/throttling events. The separate
frontier continued running. Evidence is under
`nn_meta/validation/v7-discovery-resources-20261002-r0/`: before.json,
stopped.json, deployment.json and verification.json.

14 focused tests passed for memory/CPU sizing, daytime transition, zero-admission
pressure behavior, per-worker disk reservation, verified empty inputs, retained
frontier provenance and terminal replay decisions. Real handover verified source
preservation and actual process progress. No broad training/capture rerun.

## Evidence boundary

This is a concurrency increase, not an optimized replay algorithm or a measured
speedup. Four-worker throughput still needs an overnight observation. Follow
useful cohort progress and I/O pressure; CPU utilization alone does not prove
faster completion. Completed gates remain closed and gate 7-3 remains open.
No paper/live model was deployed or order submitted by this work.
