# Twelve-worker entry capture — September 27, 2026

The user requested twelve workers after the eight-worker upgrade. A new versioned
runner supports up to 12 × 32 = **384 concurrent requests**. The running twelve-worker
configuration is retained after live measurements. Completed packs and exact
entry demand remain intact; no other V7 scope or operating service changed.

## Implementation and safeguards

- `scripts/run_v7_capture_campaign_v7.py` extends only the allowed worker ceiling
  and selects `docs/specs/V7_CAPTURE_STORAGE_V7_20260927.json`. All prior source
  hashes were checked unchanged. The unchanged v5 I/O/memory implementation is used.
- The launcher autosizes at 1 GiB per worker with a 6 GiB host reserve, capped at
  the user-selected maximum of twelve. MemoryHigh/Max remain **14 GiB**; swap is off.
  The existing shared working-memory guard backs off prefetch at 6/8/10 GiB.
- CPU quota stays **800%**, Nice=10, CPUWeight=50. Twelve worker processes do not
  mean twelve physical cores or twelve fully occupied cores. TasksMax is 464.
- Both disks retain 10 GB reserves; MRHA overflow and quota accounting are unchanged.
- Eight workers drained cleanly with no pending writes or acquisition reservations.
  The new runner reused all **38,646** prior packs before requesting new data.
- Resume via the current runner, even if reducing the worker count. Old runners
  cannot admit newly produced packs bound to the new producer.

## Observed throughput

The baseline is the preceding 180-second window. Two subsequent 45-second windows
measure twelve workers while retaining all newly captured work. These are different
adjacent ranges, not a replay of identical data. Density is shown explicitly;
short windows are evidence for the operational choice, not a reliable campaign ETA.
Response MB counts decoded HTTP response-body bytes, not wire traffic.

| Workers | Seconds | Ranges/s | Response MB/range | Response MB/s | Retained MB/s |
| --- | --- | --- | --- | --- | --- |
| 8 | 180 | 438.2 | 0.063 | 27.42 | 2.82 |
| 12 | 45 | 478.1 | 0.067 | 31.95 | 3.21 |
| 12 | 45 | 519.4 | 0.044 | 22.75 | 2.58 |

Memory, temperature, CPU utilization, guard settings and error counts for each
window are in the [dated receipt](2026-09-27-v7-twelve-worker-capture.json).
The first sample recorded memory.max reclaim events and brief CPU-quota throttling.
Inspection showed approximately 11.2 GiB of clean inactive file cache and 2.6 GiB
of anonymous memory inside the unchanged 14 GiB ceiling, with no OOM events.
The existing guard correctly kept prefetch at 32 because active working memory
was below 6 GiB. Memory-limit counters therefore do not imply that the old
cache-blind prefetch defect returned. See both windows for subsequent behavior.
All measurements are snapshots, not promises about future denser workloads.

## Validation and current state

**26 focused tests passed**, including prior-version pack reuse, scope rejection,
no duplicate quota charges, overflow recovery and cache-aware memory handling.
Shell syntax and scoped whitespace checks passed. The preceding full regression
run passed 2,514 tests and 18 subtests (one skipped); it predates this small ceiling
extension and was not repeated. No bound capture/packing/guard implementation changed.

Current pointers and the selected restart command are in
[CURRENT_STATE](../CURRENT_STATE.md#v7-acquisition-runtime):
`bash scripts/start_v7_capture_campaign_v7.sh 12 32`. Do not launch a duplicate.
To lower concurrency after a clean drain, use this same runner with `8 32`.
V7 remains at gate 7-3; acquisition is still running.
