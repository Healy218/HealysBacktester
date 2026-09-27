# V7 entry download concurrency — September 27, 2026

The user authorized speeding up the running download as much as possible.
The original four processes each performed blocking requests sequentially; a
30-second hardware sample found request waiting, not saturated CPU or SSD.

## Implementation and retained work

Versioned controller `scripts/run_v7_capture_campaign_v3.py`, I/O implementation
`scripts/v7_parallel_capture_v3.py`, and explicit-concurrency launcher
`scripts/start_v7_capture_campaign_v3.sh`. Original frozen producers are unchanged.
The original controller was interrupted in its main process only: its process
pool drained, the service became inactive, and the shared quota had no remaining
reservations before replacement. The new controller verified/reused **6,605 old
packs covering 211,122 requested ranges** at first resume, without downloading or
charging them again. All subsequent measured batches are retained production
inputs, not throwaway sample downloads.

Four autosized process workers remain the upper bound; numerical libraries still
use one thread per worker. Each process has a bounded I/O thread pool with one
persistent authenticated session per thread. Up to 16 I/O threads per worker are
permitted by the new frozen declaration. The original and new controllers share
an exclusive lock on the original state directory, preventing overlapping queues.

The pack format, exact demand, immutable prior-coverage subtraction, raw tick
verification and compression roundtrip are unchanged. Up to one leaf per active
generator is prefetched, with one 50,000-row provider page before the existing
exact recursive split. This bounds leaf size at 50,000 records while preserving
all rows, nanoseconds, conditions and quote/trade distinctions. Dense intervals
can produce more split leaves than before; the existing 256-leaf/512-MiB pack
bounds still fail closed instead of silently truncating. No full-universe claim
is inferred from measured batches.

Transient transport errors and HTTP 500/502/503/504 have bounded retries. HTTP
429 and permanent errors stop dispatch and drain; authenticated URLs/bodies are
never logged. New SIGINT/SIGTERM handling drains jobs, publishes a pause meter,
and releases quota reservations. Systemd uses KillMode=mixed and a ten-minute
stop allowance so worker processes can finish their current bounded work.

MemoryHigh 10 GiB, MemoryMax 14 GiB, no swap, CPU quota 400%, low priority, and
20 GiB disk reserve remain. TasksMax is 256 to accommodate the bounded I/O pool.
The original 100-GB campaign allocation, 250-GB acquisition cap and 640-GB project
cap are unchanged. Faster transfer does not establish the final dataset's size
or remove a capacity pause.

Massive's current official guidance says paid subscriptions have no REST request
limit for the subscribed asset class. This is not a promise of linear scaling or
unlimited server throughput: [official request-limit guidance](https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis).

## Validation

51 focused tests passed for the first parallel version; seven additional focused
checks passed for the final pagination version and prior-version pack reuse.
The original 51 checks ran across the new parallel driver, original campaign,
provider ticks and v2 packed archive. Checks include actual pack roundtrips,
old-producer receipt reuse without relabeling or duplicate charging, bounded
concurrency, failed-fetch and rejected-writer drain, exact split coverage, and
tamper rejection. Launcher Bash syntax passed. Real second resume also reuses
new-version packs and their original byte hashes. No completed demand/catalog
campaign or broad unchanged test suite was rerun.

## Dense-data refinement

The first parallel version used 5,000-row pages and four pages per leaf. A later,
denser ticker exposed redundant pagination/splitting: the 64-request setting
processed only 22.4 ranges/s in a 30-second sample, despite 1.58 CPU cores and
1.53 GB memory. Therefore that producer was preserved and drained (346 additional
packs in that run, no failed batches, quota reservations empty). Version 3 uses
one full 50,000-row page per leaf, removing the small-page round trips while
retaining a finite raw-row bound. It verifies and reuses both original and v2
pack bindings. All 858 v2 packs remain useful data. No demand or catalog work was
repeated. A larger prefetched leaf may require more memory, so final live memory
measurements are retained separately. Do not compare the earlier quiet ticker's
rate directly with the denser ticker as a controlled speedup.

## Live measurements and selected setting

Final measurements and live service configuration are recorded in the companion
`2026-09-27-v7-parallel-capture.json` and the current handoff. Rates are sequential
measurements on unfinished work; payload sizes and securities vary, so they are
not a controlled same-data benchmark or guaranteed full-run throughput. The old
measurement was roughly 20 ranges/second.

Final selected setting: **64 concurrent requests**, from four process workers
with 16 I/O threads each. Version 3's 30-second live sample reached **77.85
ranges/s**, used **1.60 GB** of cgroup memory and 2.27 CPU cores on average.
The sample saw 0.56 seconds of CPU quota throttling; this is distinct from
provider throttling. At the final evidence snapshot, 301 new v3 batches
had completed with zero failures, retries or HTTP 429s; memory pressure/OOM
counters were zero. Initial v3 resume verified **7,463 retained packs / 238,572
ranges** (original plus v2), without reacquisition. The full queue remains running.

The original ~20 ranges/s and final ~78 ranges/s observation is roughly a 4x
increase, but rates vary with request density. No guarantee of a fourfold faster
full campaign follows. Storage guards can still pause the job; no capacity
increase, final size claim or new 7-3 completion claim is made.
