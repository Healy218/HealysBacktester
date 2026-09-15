# V7 acquisition started; storage/performance paths implemented and piloted

## Running download

The user authorized starting acquisition and implementing the five performance
priorities, explicitly adding Arrow/Feather, Polars and Zarr for comparison.
They then allocated **250 GB for data downloads**. V7's model window remains
March 7, 2022–September 14, 2026; acquisition also includes 2021 warmup data.

Active unit: `healys-v7-download-20260915-budget.service`.
Active root: `nn_meta/data_v7/base-20260915r4/`.
Status: `status.json` in that root; budget ledger: `nn_meta/data_v7/quota.json`.
Four spawned processes, one inner numerical/I/O thread each, 8 GiB memory
maximum (7 GiB high), no swap, CPU quota 300%, nice 15, 100 GiB free-space
reserve. The persistent user service is installed and enabled for reboot
resume. Its current running instance was created with `systemd-run`; enabling
by the installed absolute service path succeeded. Normal manual restart uses
`systemctl --user restart healys-v7-download-20260915-budget.service`.

The 250 GB cap means **250,000,000,000 bytes**, not 250 GiB. Each task reserves
1 GiB under a cross-process lock before writing, returns unused capacity and
charges actual retained bytes including failed attempts. Hardlinked reuse is
counted once on recovery. Stock pages have a conservative pre-write size
bound; S3 ContentLength is checked before writing. Capacity exhaustion stops
new submissions and reports `paused_capacity`, rather than claiming completion.
The downloader also stops after 20 task failures. Capacity pauses and interrupted
tasks can be resumed after resolving the cause; they are not research coverage.

The shared budget covers files acquired under `nn_meta/data_v7`, including
base raw/decoded captures and quote captures. Performance-test artifacts under
`nn_meta/validation` are separate working outputs, not bulk acquisition.
Do not start a second base controller or reset the quota ledger while quote
capture workers are active. The base controller has an exclusive acquisition
lock; initialization reconciles retained bytes/reservations after interruption.

The 8,284 base tasks cover:

- Alpaca SIP raw and all-adjusted **1Min** stock pages by symbol/year, with
  complete pagination and explicit `asof=-` to preserve literal ticker roots.
- All-market MASSIVE option day and minute aggregate gzip objects for the
  captured calendar's trading days, retained without collapsing to 15 minutes.
- An independently captured Alpaca calendar for 2021-01-01–2026-09-14.

The 449-symbol reference is expanded to explicitly acquire known old roots
SQ/FI/BITF and exchange-form BRK.B (BRKB is fetched as BRK.B), producing 452
literal fetch symbols. This is not a completed historical universe/alias audit.
Observed-empty symbol-years are recorded, not silently called complete listing
coverage. Raw pages retain provider capture vintages; adjusted history still
needs the final corporate-action and feature-availability audit.

First stock pilot: **212,907** SPY 2022 minute bars in each price basis. After
fixing the boto StreamingBody context-manager adapter, both March 7, 2022
option aggregate objects downloaded and passed gzip CRC/length/hash checks.
The failed first attempt is preserved. The capped launch hardlinked 299
completed task directories and verifies receipts before reuse. All code used
by the active service is copied under its root's `source/`; do not edit that
copy or relabel old checkpoints.

## What was reusable from the old flat files

The inspected old caches retain 500 daily **15-minute** option partitions, with
no original gzip minute archives in those locations. Those files remain valid
for V6 and compatible contextual reuse. They cannot recover minute trade bars
or historical bid/ask spreads. New downloads are a separate immutable archive;
no old cache/model/paper release was overwritten.

## Implemented performance paths

| Priority | Implementation and current boundary |
|---|---|
| Shared indicators | `nn_meta/v7/signals.py` computes unique MA windows once per symbol/timeframe, then emits bounded vectorbt crossover batches. Exact parity with the existing vectorbt generator and batch-size invariance are tested. Other families still require their V7 adapters. |
| Shared quote captures | `nn_meta/v7/quotes.py` unions overlapping requests by contract/kind within bounded time cells, retaining every original request and its capture memberships. `scripts/capture_v7_quotes.py` executes bounded batches, preserves complete raw receipts, verifies reuse, and charges the same 250 GB budget. |
| Bounded processing/output | `nn_meta/v7/bars.py` uses Polars lazy scans and streamed Parquet output, aligns 1/5/15/30-minute bars to captured sessions and exposes missing-minute counts. Table writers stream Arrow/Parquet batches; signal serialization is capped at 65,536 events per batch. No whole-universe pandas concatenation. |
| Shared immutable arrays | `nn_meta/v7/storage.py` writes/read-validates NumPy memory maps and chunked Zarr arrays, with immutable commit receipts, numerical dtype/shape/column identities and read-only readers. Existing prepared-fold training semantics remain available; a V7 full-feature fold/model runner is not yet admitted. |
| Measured backend choice | `scripts/benchmark_v7_storage.py` compares real-shard Parquet, Arrow IPC, NumPy and Zarr; includes output parity, actual data consumption, write/verification time, disk size and per-process peak RSS. `scripts/build_v7_working_set.py` integrates the paths in a four-timeframe MA pilot. |

IPC is the Arrow file format underlying Feather V2. This implementation uses
uncompressed IPC `.arrow` working files. Zarr is pinned to **2.18.7** and
numcodecs to **0.15.1**, preserving NumPy **1.26.4** and the existing
vectorbt/TensorFlow stack. Polars **1.44.2** was installed. Exact requested
packages are in `requirements-v7.txt`; PyArrow was already present.

`nn_meta/v7/runtime.py` uses `spawn` and explicit one-thread limits for Blosc,
Arrow, Polars and numerical libraries. It refuses a Polars thread pool already
initialized above the requested limit. No `MALLOC_CONF`, allocator preload,
mount or THP change was made. Arrow reports mimalloc; THP is already enabled.

## Real measurements

SPY 2022, 212,907 observed minute rows, five float64 OHLCV columns. Three warm
reads per format consume/hash all numerical values. Concurrent acquisition
was running; these are component timings, not cold-cache or full-build results.

| Store | Write + durable commit | Median warm read + consume | Stored size |
|---|---:|---:|---:|
| Parquet/Zstd | 0.0439 s | 0.0068 s | 2.57 MB |
| Arrow IPC | 0.0259 s | 0.0042 s | 8.52 MB |
| NumPy mmap | 0.0307 s | 0.0033 s | 8.52 MB |
| Zarr/Zstd | 0.0663 s | 0.0078 s | 4.69 MB |

All decoded numerical hashes match. IPC warm reads were about 1.6x faster
than Parquet at 3.3x size. NumPy maps were fastest in this sample; Zarr was
slower. Keep Zarr selectable, not the assumed winner for all data shapes.

Polars calendar/session aggregation across 1/5/15/30 minutes took 0.099/0.065/
0.061/0.062 seconds versus 0.655/0.641/0.638/0.651 for the tested pandas
session-loop reference. Outputs matched (float tolerance 1e-12). Polars timing
includes read and pandas conversion; the pandas input was already loaded.
The observed 6.6–10.5x applies to these implementations of this transform.

Four spawned working-set pilot workers used Arrow signals and Zarr shared MA
arrays, **64 explicitly selected MA variants per timeframe**. RTH bars:
97,710 / 19,542 / 6,514 / 3,257. Each worker computed shared MAs once and
streamed 743,958 / 137,050 / 43,880 / 21,080 signal events. Peak process RSS
was approximately 759/526/486/485 MiB, including interpreter/native libraries.
No unobserved minute buckets were found in this SPY sample. This is not a
full-feature/full-option/full-universe build pilot.

Quote access/reuse pilot: SPY220311C00420000, March 7, 2022 14:31–14:36 UTC.
Three requests became two captures (one shared quote request and one trade
request): **1,432 quotes, 2 trades**. A repeat reused both verified captures.
This is an access/union test; it is not a PIT contract-selection or fill audit.

Evidence: `nn_meta/validation/v7-storage-20260915/report.json`,
`nn_meta/validation/v7-working-pilot-20260915r2/report.json`,
`nn_meta/data_v7/quote-access-pilot-20260915/report.json`, and
`nn_meta/validation/v7-download-performance-status-20260915.json`.

## Validation and remaining work

Repository suite: **1,646 tests and 18 subtests passed**, 18 dependency warnings.
Focused tests cover page ordering/OHLC integrity, receipt tampering, capacity
reservation/hardlink accounting, immutable stores, null/dtype round trips,
quote union memberships, vectorbt/batch parity and calendar aggregation/gaps.
The final metadata-reservation change passed the real capture reuse path;
the final shared-column metadata passed the repeated working-set pilot.
The generated persistent systemd unit passed verification.

Next: finish base acquisition; validate listing/alias/calendar/stock gaps;
extend full strategy/timeframe adapters and full feature dependencies;
generate the complete outcome-independent contract/time request inventory;
capture full execution/mark/roll quotes; implement/audit quote labels and
portfolio accounting; freeze purged V7 folds; then run representative complete
pipeline/resource pilots before a full build and training. No V7 model has
been trained, and no end-to-end speedup or market-performance claim is made.

## September 15 continuation: coverage pilot

Verified both SPY 2022 raw/all completion receipts and every referenced file.
The 212,907 timestamps match exactly across price bases. Against the captured
calendar, all 251 regular sessions contain all 97,710 expected minute starts;
no regular-session minute is missing. This is a presence check, not a
corporate-action adjustment/PIT-vintage audit or full-universe admission.
Evidence: `nn_meta/validation/v7-coverage-pilot-20260915/report.json`.

At 05:47:21 UTC, acquisition reached 2,500/8,284 completed tasks and 15.98 GB
charged, with one failure. The service journal identifies
`options/day_aggs/2026-09-14`: `Massive object download failed (NoSuchKey)`.
The requested final-session daily object was unavailable at that request;
publication delay is a possibility, not verified. Acquisition continues on
other tasks. Recheck/retry this object after the current four-worker run
drains; the failure blocks complete aggregate coverage until resolved.
