# Eight-worker entry capture — September 27, 2026

The user authorized a six-worker/192-request trial, followed by eight workers/
256 requests if useful throughput improved. Eight workers are selected after
both trials completed without capture errors, retries or provider throttling.
The running campaign retains the original input scope and completed data.

## Change and preservation

- Versioned runner/launcher `scripts/run_v7_capture_campaign_v6.py` and
  `scripts/start_v7_capture_campaign_v6.sh`; prior producers remain byte-identical.
- Policy `docs/specs/V7_CAPTURE_STORAGE_V6_20260927.json` authorizes up to eight
  process workers. The old source-bound policy remains intact.
- Reuses the v5 I/O implementation, packing, validation, memory guard and storage
  routing. Six workers reused all 27,894 prior packs. Eight workers then reused
  all 28,891 packs, including the 997 newly completed by six workers.
- Both transitions drained cleanly with zero pending batches and zero acquisition
  reservations. No data was reset, relabeled or deliberately downloaded twice.
- Worker count is autosized using 1.5 GiB/worker and 6 GiB system reserve, capped
  by the requested measured ceiling. MemoryHigh/Max remain 14 GiB, swap remains
  disabled, and clean-cache-aware prefetch backoff remains 6/8/10 GiB.
- CPU quota remains 800%, Nice=10, CPUWeight=50. TasksMax scales with workers and
  threads: 320 at eight workers. Local/MRHA reserves remain 10 decimal GB each.

## Measurements

Existing completed-attempt journals provide the four-worker baseline. Live
45-second observation windows measure six/eight workers; the full regression
suite finished before the live sampling windows. Each trial downloads new
required ranges and keeps them. The first six-worker window overlaps the end
of resume/startup; use the density column when comparing samples.
Response MB means decoded HTTP response-body bytes, not measured wire traffic.

| Workers | Seconds | Ranges/s | Response MB/range | Response MB/s | Retained MB/s |
| --- | --- | --- | --- | --- | --- |
| 4 | 300 | 146.8 | 0.148 | 21.73 | 1.66 |
| 6 | 45 | 289.4 | 0.105 | 30.41 | 2.64 |
| 6 | 45 | 208.1 | 0.182 | 37.87 | 2.67 |
| 8 | 45 | 381.8 | 0.095 | 36.36 | 3.24 |
| 8 | 45 | 371.2 | 0.091 | 33.62 | 3.20 |

The first six/eight-worker samples have similar response density. Eight workers
improve both response-body and retained-data throughput there. These are adjacent
live workloads, not a controlled replay of identical requests or a guaranteed
whole-campaign speedup. Data density changes substantially across the queue;
do not project these short samples as a reliable completion time.

Both six/eight-worker observation windows stayed at the full 32-prefetch ceiling
per worker, with zero CPU-quota throttling, memory-limit events, failed batches,
retries or HTTP 429s. The memory guard can lower concurrency on denser future
ranges; 256 is a ceiling, not a claim of constant simultaneous HTTP activity.
Detailed measurements and the dated progress snapshot are in the
[receipt](2026-09-27-v7-eight-worker-capture.json). Raw attempt windows remain in
`nn_meta/validation/v7-concurrency-20260927/`.

## Validation and operation

24 focused capture/storage/memory/concurrency tests passed. The full suite
passed: **2,514 tests, 1 skipped, and 18 subtests**. New checks prove v5 packs
are reused without refetching, relabeling or recharging; changed scopes are
rejected; newly captured overflow packs remain reusable with one quota charge.
Shell syntax and the scoped whitespace check passed.

Current service, receipt paths and restart command are owned by
[CURRENT_STATE](../CURRENT_STATE.md#v7-acquisition-runtime). Resume command:
`bash scripts/start_v7_capture_campaign_v6.sh 8 32`. Do not launch a duplicate.
The same versioned runner supports `6 32` or `4 32` after a clean drain if future
measurements justify a reduction; do not resume v5 over new v6-produced packs.
V7 remains at gate 7-3; no assembly, training or unrelated operating service changed.
