# V7-3 bounded performance revision — October 2, 2026

## Scope and result

User authorized profiling, optimizing measured bottlenecks, exact/restart parity
and worker scaling after the V6 ten-minute policy deployment. The selected V7
campaign remains paused. All runs here use independent copies under
`nn_meta/validation/v7-performance-20261002-r0`; none advances the selected waves.
This validates a performance revision on bounded samples, not full 591-security
completion, full-scope resource sizing or deployment of a new controller.

The three discovery samples retain a small partial checkpoint, a long completed
prefix and a large database: BBG000C3HSR0, BBG000BB5006 and BBG000BCMBG4. Exact
next-cohort comparisons use 40 initial cohorts followed by two 200-cohort runs,
with the second timing round reversing old/new execution order. The selected
source receipts and all scientific inputs remain unchanged.

Across six unprofiled resumed comparisons (1,200 new cohorts per engine), old
wall time totals 94.62 seconds and optimized time totals 59.45 seconds: **1.59×**
throughput, or 37.2% less elapsed time. Individual matched ratios range 1.25–1.98×.
These samples differ in work per cohort; this is not a reliable whole-universe
ETA. They include initialization, bounded execution, durable writes and final
input verification. Cold OS caches were not forcibly cleared during trading.
The cache-order reversal reduces one measurement bias but does not eliminate all
host/load variation. The old overnight rate cannot be multiplied by this sample
speedup and presented as a guaranteed completion date.

## Measured changes

- Initial large-database profile spent 5.98 of 17.65 seconds reporting progress
  through grouped full-table scans. New transactional summary tables/triggers
  initialize from inherited scientific tables once; subsequent reports read
  those counters. Inserts and summaries share one SQLite transaction.
- A resume cursor commits with each durable batch. It starts unset for inherited
  checkpoints, so it never assumes that the largest completed key proves an
  unbroken prefix. Subsequent source reads seek by indexed symbol/decision key;
  both option sides at the boundary remain accounted for.
- Up to eight cohorts share a synchronous=FULL commit. Progress reports and normal
  exit flush the batch. A crash can require replaying the uncommitted batch;
  committed work and its counters/cursor survive together.
- Packed quote windows bisect verified ordered timestamps instead of repeatedly
  filtering the whole decoded capture. Nested records are still copied on return,
  preserving isolation and exact duplicate/boundary behavior. The bounded pack
  cache increases from two to four; receipt and payload verification remain.
- Pending replay validates every plan key/target, but checks completed keys before
  fetching their source rows. A matching resumed 200-cohort replay took 15.86s old
  versus 13.04s optimized (1.22×); optimized ran first in that comparison.

Large checkpoint imports intentionally copy/recover/verify inherited databases
and initialize derived summaries. Initial optimized runs including that one-time
cost took 33.37s and 29.57s versus 18.59s and 17.65s baseline on the two large
samples. That migration cost is reported separately from recurring throughput.
Repeated process startup was observed but was not the largest measured recurring
cost; persistent worker scheduling is not implemented by this revision.

## Validation and execution boundary

All six scientific tables—cohorts, contents, buckets, exclusions, pending and
links—match exactly by ordered row hash after the initial and resumed discovery
runs. This checks compressed result bytes and exact memberships, not only counts.
Pending replay also matches after 40 and 240 newly processed cohorts. Tests cover
inherited gaps, same-timestamp option sides, duplicate replay plans, transaction
rollback, abrupt process exit, exact quote-window slicing and nested mutation
isolation. Selected raw packs, contracts and scientific source modules stay frozen.

New consumers: `scripts/discover_v7_execution_wave_v3.py` and
`scripts/replay_v7_pending_wave_v2.py`. New source-bound modules:
`wave_performance_v1.py`, `packed_quote_index_v2.py`, `packed_quotes_v3.py`.
Inheritance records the predecessor declaration, binding and database hashes;
old wave declarations are never rewritten to accept a different producer.

Reproduction tools: `scripts/benchmark_v7_wave_v1.py` prepares isolated seeds and
profiles first runs; `scripts/measure_v7_wave_v1.py` compares resumed work, exact
outputs, replay and concurrency; `scripts/check_v7_wave_kill_resume_v1.py` checks
an actual killed producer against an uninterrupted bounded reference.
Do not rerun those commands over existing evidence directories or the selected
campaign. Use a separately named validation revision for another experiment.

The balanced eight-task queue (1,600 benchmark cohorts, including repeated
checkpoint replicas) took 81.10s with one worker, 49.50s with two and 37.98s with
four. That is 2.14× one-worker throughput and 1.30× two-worker throughput. The
shorter four-task queue was dominated by one long task and did not distinguish
two from four workers; it is retained as a load-balance limitation, not hidden.
Autosize admitted four with a measured-sample 1.5GiB allowance per worker and an
18GiB host/V6 reserve. Per-process RSS in the resumed comparisons was about
438–485MiB. These are sample measurements, not full-scope memory maxima; existing
production admission policy remains unchanged. All scaling outputs match.

An actual SIGKILL test interrupted the producer after 64 newly committed cohorts.
Its hot-journal preimage was preserved, it resumed the remaining 136 cohorts, and
all six scientific tables matched the uninterrupted 200-cohort reference exactly.
Eleven focused performance/quote/cohort tests passed in addition to the actual
benchmark comparisons. Hashes confirm the three selected original databases are
unchanged from their prepared seeds.

Final evidence: `nn_meta/validation/v7-performance-20261002-r0/summary.json`;
detailed timing/profile/parity receipts remain alongside it. No gate closure or broad
resume follows automatically from a successful benchmark. Production adoption
still needs a new controller/declaration lineage that imports retained checkpoints,
then explicit resumption of the paused campaign.
