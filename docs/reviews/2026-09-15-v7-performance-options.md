# V7 performance options: priorities before changing storage or Linux settings

Assessment based on current checkout and read-only host inspection, September
15 UTC, 2026. No storage backend, allocator override, sysctl or mount was changed.
No 5–20x end-to-end speedup has been measured or promised.

## Existing implementation and machine state

- Data/mark checkpoints already use Parquet/PyArrow. Strategy and provenance
  manifests use JSON; the build is not principally serializing giant pickles.
- `nn_meta/training_jobs.py` already prepares fold matrices once, in bounded
  batches, writes `.npy` files and loads them read-only with `mmap_mode='r'`
  in worker processes. Model-library processing can still allocate its own
  working memory; this is not a claim of zero-copy training end to end.
- PyArrow 25.0.1 reports allocator `mimalloc`, with mimalloc/jemalloc/system
  backends available. This describes Arrow's pool, not every allocation in
  CPython, NumPy, TensorFlow or LightGBM.
- `/tmp` is already tmpfs with a 15.2 GiB size limit. The limit is not reserved
  or additional RAM. Four compute workers and the paper producer share the
  host's roughly 30 GiB usable memory with tmpfs and page cache.
- Transparent hugepages: `enabled=always`, `defrag=defer+madvise`. This does
  not prove every array allocation actually uses huge pages.
- Polars, Zarr and safetensors are not installed in this venv; h5py and msgpack
  are present. Installing a library does not establish a useful speedup.

## Evaluation of the proposed changes

| Option | Decision for V7 |
|---|---|
| Arrow IPC / uncompressed Feather memory maps | Benchmark for immutable, repeatedly read working data. Keep durable compressed Parquet checkpoints/raw provenance. Existing `.npy` maps may already be best for dense matrices. |
| Polars | Benchmark lazy filtered reads, joins, group-bys and bounded output against PyArrow/pandas. Include conversion to vectorbt's pandas/NumPy inputs in the timing and memory accounting. |
| Zarr | Consider if dense chunked arrays need selective or incremental access beyond current `.npy` maps. Raw quote events are naturally timestamped table rows; an array store is not automatically the right format. |
| HDF5 | Defer as the default shared multi-worker sink. Ordinary h5py SWMR has one writer; multi-writer Parallel HDF5 requires the MPI-enabled stack and coordinated operations. |
| Msgpack | Low priority for small strategy/configuration manifests unless profiling identifies decoding as material. Preserve transparent canonical JSON identities/provenance. |
| Safetensors | A tensor storage format, not an arbitrary Python strategy-dictionary replacement. Current GBT model artifacts and metadata do not justify migration. |
| tmpfs checkpoints | Keep completed resumable artifacts on NVMe. A small, explicitly capped disposable scratch cache is optional if measurements justify it. Periodic copying from RAM leaves an interval of lost work after reboot/crash. |
| THP | Already enabled. Defer global tuning; any isolated experiment must measure both build throughput and paper-producer latency under memory pressure. |
| mimalloc / jemalloc | Arrow already uses mimalloc. Test process-local alternatives only after identifying allocation/fragmentation costs; do not globally preload an allocator as an assumed cure. |

Arrow's zero-copy reads apply to compatible memory-mapped IPC buffers; compressed
payloads need decompression and pandas/NumPy conversion can copy. Memory mapping
still incurs actual page reads when data is touched. See [Arrow IPC](https://arrow.apache.org/docs/python/ipc.html)
and [pandas integration](https://arrow.apache.org/docs/python/pandas.html).

Polars' documented advantages include predicate/projection pushdown and common
subexpression elimination, not a universal speed multiplier for rewriting
every file. See [lazy optimizations](https://docs.pola.rs/user-guide/lazy/optimizations/).

Concurrent writes require explicit ownership: for Zarr, disjoint chunks and
appropriate atomic storage, with shard-level coordination when sharing physical
shards; for HDF5, suitable MPI support or one writer. See [Zarr performance](https://zarr.readthedocs.io/en/v3.2.0/user-guide/performance.html),
[h5py Parallel HDF5](https://docs.h5py.org/en/stable/mpi.html) and
[HDF5 SWMR](https://support.hdfgroup.org/documentation/hdf5-docs/advanced_topics/intro_SWMR.html).
Safetensors is specifically for [tensor storage](https://huggingface.co/docs/safetensors/index).
[THP policy](https://www.kernel.org/doc/html/latest/admin-guide/mm/transhuge.html)
and [allocator behavior](https://github.com/microsoft/mimalloc) require workload-specific assessment.

## Prioritized V7 implementation and benchmark plan

1. Record wall/CPU time, peak resident and proportional shared memory, cgroup
   memory, bytes read/written, API wait/retries and stage/worker counts. Separate
   quote acquisition, integrity verification, signals, features, execution,
   assembly, fold preparation and fitting. Preserve all correctness checks.
2. Avoid redundant work: compute common indicators once per symbol/timeframe,
   cache verified results with full numerical/context identities, union quote
   requests before capture, and reuse immutable contract/time observations
   across variant execution paths without merging distinct portfolio decisions.
3. Use bounded variant batches and partitioned rows/marks. Avoid reintroducing
   the old all-shards pandas concatenation that exceeded memory. Read only
   required columns/time ranges and write bounded batches.
4. Benchmark Parquet versus IPC versus existing NumPy maps on real stock,
   quote and feature shards. Measure initial conversion, complete data access,
   cold versus warm reads, four-process reuse, disk footprint and peak memory.
   Do not time just opening a memory map against actually decoding a file.
5. Compare a bounded Polars transformation pipeline, including vectorbt
   conversion costs. Keep it only if full outputs, timestamps, nulls, ordering
   and point-in-time joins match and end-to-end resource use improves.
6. Retain four outer processes with bounded Arrow/BLAS/Numba/model inner
   threads. Tune against measured memory, disk throughput and paper-runtime
   headroom rather than allowing every library to use all cores per worker.
7. After a representative end-to-end pilot, freeze the chosen layout/runtime
   and resource policy with V7. Throughput improvements do not authorize
   altering signal/feature/execution semantics or skipping data verification.

A faster serializer only speeds up the time spent serializing. For example,
if that stage were 20% of runtime, making it 10x faster would reduce total
runtime by 18%, about a 1.22x overall speedup. Those are illustrative numbers,
not a profile of this pipeline. Actual V7 bottlenecks remain to be measured.
