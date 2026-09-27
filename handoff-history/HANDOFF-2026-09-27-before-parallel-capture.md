# Handoff — September 27, 2026 — V7-4 integration connected

Read TODO first. The user challenged repeated work, then authorized starting
7-4 alongside the running V7-3 downloads. Advance existing receipts; do not
restart preparation or repeat old component pilots. Needed provider downloads
and MRHA use remain authorized. Work on main; protect V6 and unrelated dirty work.

## What changed this session

Added a versioned shared execution runner using the existing PhysicalLedger,
retained option paths, captured option/stock quotes, reported settlement dates,
final 4,918 cash events, split/rename inputs and noncash guards. It stops at the
first missing admitted dependency while retaining cash, holdings and reservations.
Missing future outcomes do not filter allocation; rejected paths do not block it.
Original portfolio/physical/replay/downloader/assembly producers are unchanged.

[Implementation, real evidence and limits](docs/reviews/2026-09-27-v7-integrated-execution.md).
58 focused tests pass; Bash syntax and actual retained-ledger resume comparison
pass. No broad suite or old preparation campaign was repeated. New source files
are bound by these runs: preserve them or version subsequent behavior changes.

## Latest authoritative integration artifacts

All shortened roots are under `nn_meta/validation/`:

- Shared ledger: `v7-integrated-execution-20260927-r2`.
- Quote index: `v7-integrated-quote-index-20260927-r2`.
- Actual source paths: `v7-execution-discovery-20260927-r13`.
- First index reused 3,522 entry packs plus 72 prior packs, 114,062 captures.
- Added exact NVDA window: `nn_meta/data_v7/integrated-frontier-20260927-r1`,
  19,068 bytes. No overlapping entry queue was launched.

The shared account completed DIS and ABBV; NVDA remains open. Cash is
$87,596.26474814238, no settlement commitments. The first resume preserves all
1,466 ledger events, three decisions and 164 earlier marks and adds one mark.
The next shared quote request is NVDA240322C00910000 over
[1711038150000000000, 1711038180000000001), recorded in the integrated
`capture-requests.json`. Source r13 retains the later VKTX/FUTU requests too.

Run the integration with current input bindings using:

```bash
bash scripts/run_v7_integrated_execution.sh \
  nn_meta/validation/v7-execution-discovery-20260927-r13 \
  nn_meta/validation/v7-integrated-quote-index-20260927-r2 \
  nn_meta/validation/NEW-INTEGRATED-OUTPUT
```

Use the existing exact-gap capture and replay machinery for new data, preserving
old outputs. New source discovery outputs start at r14, quote index/shared ledger
outputs at r3. The runner consumes retained paths; it is not a full-universe
automatic path-generation/download service. It does not generate model labels
for the full universe. Full V7-4 remains open; **no real physical exercise or
stock liquidation occurred in this five-path run**. Unit tests cover those
connections, but do not establish full real-data coverage.

## Flat-file versus tick clarification

The user asked why additional downloads are needed after option flat files were
captured. Directly inspected a retained V7 daily aggregate gzip header:
ticker, volume, open, close, high, low, window_start, transactions. It contains
no bid/ask quotes. Legacy flat-file ingestion also retained 15-minute OHLCV
partitions; these do not recover event-level quote/trade history. Existing bars
remain inputs; the live capture adds exact quote/trade windows used by midpoint
execution, premium stops and the current tick-feature contract.

There is **no verified 300 GB additional-data requirement**. The existing packed
entry estimate including routing is 142.389 GB, or 173.954 GB at mean plus three
sample standard errors (not an upper bound). Dated references had a 1.739 GB
planning allowance. The 250 GB figure is a shared acquisition cap including
already retained data (about 72.44 GB at this check), not another 250 GB order.
The live 100 GB dispatch allocation is also not a final size estimate. Actual
additional held-path/assembly/training requirements remain to be measured.
Do not confuse full aggregate history with complete bid/ask tick coverage, or
present a budget as an estimated additional requirement. No job was changed.

## Download throughput diagnosis — September 27

The user asked why entry acquisition takes days and whether hardware is limiting.
A read-only 30-second host sample found service CPU 0.157 cores, no CPU throttling,
host CPU 2.79% busy, I/O wait 0.30%, NVMe 5.07% busy at 2.431 MB/s writes and
0.002 MB/s reads. Host Ethernet received 2.106 Mbps. Four workers spent 115/120
sample points in socket-style poll waits; CPU and SSD bandwidth were not saturated.
These measurements do not independently measure the internet connection ceiling
or prove the provider's maximum allowed request rate.

The controller allows four workers; each worker sends sequential blocking HTTP
requests within its 32-range batch. Recent 200 batches all completed, with no
splits/failures; median 4.945 seconds and mean 4.988 seconds per batch. Current
throughput is therefore dominated by small-request waiting and four-way
concurrency, rather than CPU or disk throughput. The six-day estimate extrapolated
~20 ranges/second over ~10.94 million joined ranges. Faster safe request concurrency
is a candidate optimization, but no increase/provider-limit claim was tested.
No live producer, worker count, quota or job was changed. Any optimization must
be versioned, preserve retained packs and cap/reserve rules, and measure actual
provider behavior rather than assume linear scaling.
Evidence: `docs/reviews/2026-09-27-v7-download-throughput.json`.

## V7-3 live download and remaining inputs

Service `healys-v7-capture-20260927.service` is still running. At 18:07:52 UTC:
4,194 new batches, four reused; 134,052 ranges; 3,097,079,205 retained bytes;
no stop reason and zero restarts. Service RAM about 3.23 GiB; disk 264 GiB free.
Average entry rate since launch is 19.63 ranges/s: approximately 1.23% of the
original 10,941,828 joined ranges, with a rough 6.4-day entry-only remainder
at that rate. This is not exact coverage or a full V7-3 ETA; request sizes vary.
The routine status check changed no running job or acquisition plan. Check its current meter/journal before any action. Do not start
a duplicate or modify its bound producer. Frozen declaration and meter:
`nn_meta/validation/v7-entry-campaign-20260927/`; packs:
`nn_meta/data_v7/entry-campaign-20260927/`.

The service handles entries only. Dated-reference demand is complete; existing
receipt stores cover 720 of 2,223,844 planned pairs (715 valid plus five exact
blackouts). The older 516 receipts add no current entry-plan coverage.
[Receipt verification](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md).
Capture only exact additional held/exit/roll/stock gaps encountered by existing
replay after subtracting retained coverage. Do not turn conditional stock
requirements into a blanket new capture or implementation campaign.

Keep 250 GB shared acquisition / 640 GB project / 20 GiB free reserve. The live
100 GB allocation and 490 GB baseline allowance are dispatch guards, not total
size estimates. Four workers, one thread each, 10 GiB MemoryHigh / 14 GiB Max,
no swap, 400% CPU quota, low priority. MRHA capacity use is authorized.

## Completed work and guardrails

V7-1/2, 591 demand stores, request union, packing/index readers, dated hours,
five blackouts, dated-reference plan, storage cleanup and original r0–r12
execution/resume evidence are complete. Use ROADMAP's completion ledger and
`docs/V7_CURRENT_STATE.md`; do not recreate these components. The new integrated
runner is another completed component, not evidence that all real paths finished.

Preserve frozen bytes, partial ledgers and existing compatibility proofs. The
V7-2 gate uses gate.json. Existing dirty/untracked assembly.py/dataset_inputs.py
and the broad unrelated backlog remain untouched. No live V6/broker changes,
submissions or training launches. Next milestones remain full execution coverage,
7-5 assembly/folds, 7-6 resource/recovery and 7-7 current readiness/training.
The October 2 Massive decision, Alpaca integration and incubator work remain
separate TODO items.
