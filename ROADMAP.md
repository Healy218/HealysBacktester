# Roadmap — current direction and completed work

Updated September 27, 2026. The immediate objective is to finish V7 data and
launch its predeclared training campaign. **7-1 and 7-2 are complete; 7-3 real
entry downloads are running. Model training has not started.**

[TODO](TODO.md) contains unfinished tasks only. [HANDOFF](HANDOFF.md) gives the
next session's commands and pointers. [Current state](docs/V7_CURRENT_STATE.md)
identifies authoritative input receipts and download locations. The year-end
maturity target remains ≥7/10 in each [GOALS](GOALS.md) area by December 31, 2026.

## Remaining direction

Finish required option data (7-3), integrate existing execution components
(7-4), assemble rows/folds and connect trials (7-5), establish actual resource
and recovery feasibility (7-6), then pass the current readiness gate and launch
training (7-7). These are separate from completed components listed below.
Dependencies may be connected while downloads run; do not reopen completed
research campaigns or add unrelated research prerequisites.

## Completed work

### V7-1 — identity, corporate actions and held-boundary policy

**Complete September 18 under the recorded admission policies.** Historical
membership/aliases, sectors, ordinary actions, splits and cash treatment have
source-bound implementations. Dividend work finished with 4,918 payment leaves
across 4,854 price events, zero outstanding dividend cases. All 234 remaining
noncash records received explicit boundary exclusions consumed by features and
held-position guards. Do not resume older lists of 492/444/154 dividend cases.

The funded stock ledger, split/rename/cash handlers, observed stock quote
consumer and settlement transition/calendar components already exist, with
real captured component evidence. Full V7 portfolio integration remains a
separate later gate; it is not permission to rewrite these components.

Evidence: [dividend completion](docs/reviews/2026-09-18-v7-dividends-complete.md),
[7-1 closure](docs/reviews/2026-09-18-v7-6-1-closure.md),
`nn_meta/validation/v7-noncash-admission-20260918`.

### V7-2 — complete causal context and frozen proposal catalog

**Complete September 25.** All 591 securities, 1,773 5/15/30 proposal stores,
8,451 variants per security and 221-column downstream schema are preserved.
Full causal daily/market context has 667,239 rows and 1,182 passing historical
prefix replays. The historical-loader and exact kernel-recovery proofs preserve
original stores; do not refreeze to satisfy old source/runtime expectations.

Completion: `nn_meta/validation/v7-2-completion-20260925/complete.json` with
`gate.json` (not `report.json`). [Completion review](docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md).
The prerequisite live V6 repair is complete; it is not a new V7 prerequisite.

### V7-3 completed preparation — reuse, do not repeat

| Completed deliverable | Result | Evidence |
| --- | --- | --- |
| Full entry-demand scheduler and run | 591 sealed checkpoints; 793,394,264 original proposals | [Demand launch/recovery](docs/reviews/2026-09-25-v7-3-crash-recovery.md) |
| Full request census and exact joining | 76,910,536 requests; 10,941,828 contiguous ranges; no added seconds | [Union](docs/reviews/2026-09-26-v7-entry-union-and-first-capture.md), [joining](docs/reviews/2026-09-26-v7-capture-storage-forecast.md) |
| Storage cleanup and MRHA migration | 31.67 GB measured reflink saving; 9,541,723 old V6 files archived in 454 verified bundles; 35.11 GB on MRHA | [Completed migration](docs/reviews/2026-09-26-authorized-storage-reclamation.md) |
| Lossless packing and indexed reads | V2 writer/reader implemented; 1,440 sampled captures, 1,168,551 records; 12,760 original request checks | [Packed evidence](docs/reviews/2026-09-27-v7-joined-packed-capture.md) |
| Entry storage measurement | 142.39 GB mean with routing; 173.95 GB mean+3SE; 175.69 GB with reference allowance | Same packed review; entry-only, not total training size |
| Dated-reference demand | Exact 2,223,844 entry contract/dates and 301,213 root/dates | `v7-dated-reference-demand-20260927` |
| Five missing-reference treatments | Exact dated blackouts implemented; sampled references resolve to 715 standard + five blackouts | [Blackouts](docs/reviews/2026-09-27-v7-contract-reference-blackouts.md) |
| Historical regular option hours | All 301,213 entry root/dates; 576 roots; 18 dated changes; 2,370 early-close pairs | [Hours and paths](docs/reviews/2026-09-27-v7-dated-hours-and-execution-paths.md) |
| First-leg envelope census | All 591 securities; 5,867,251 possible contract/dates | Same review; potential demand, not a capture order |
| Actual replay frontier and resume | Implemented exact-gap capture/bounded prefetch; r0–r12 retain all five paths; DIS/ABBV closed, three paths pending | Same review; 60 prefix and 21 completed-label comparisons pass |
| Persistent full-universe entry capture controller | Real download launched September 27; completed packs reused after resume | [Live capture launch](docs/reviews/2026-09-27-v7-entry-campaign-started.md) |
| Live disk allocation, MRHA overflow and 14 GiB concurrency | Deployed; 8,704 prior packs reused, four real overflow batches read back; 16 focused checks | [Storage/memory review](docs/reviews/2026-09-27-v7-storage-and-memory.md) |
| Concurrent entry download with immutable resume | Versioned I/O upgrade; original 6,605 packs reused; 51 focused checks pass | [Concurrency review](docs/reviews/2026-09-27-v7-parallel-capture.md) |

The ~1 TB all-possible-first-leg scenario is **not** a measured storage
requirement or download plan. The cleanup/compression gains are real. Full
execution and training storage still need reconciliation against actual inputs.
The running download does not make full V7-3 complete; unfinished tasks are
listed once, in TODO.

### Existing V7 execution, dataset and model components

Observed option fills/marks, midpoint stops, rolls, ITM handling, physical ledger,
shared-capital replay, causal tick features, factorized row storage, fold purging,
train-only preprocessing and finite model trials are implemented components.
Some assembly adapters remain preexisting untracked local work. Preserve them.
Full assembled data and an admitted full model run are different deliverables;
complete the connections and real inputs instead of recreating components.
The last broad regression pass was 2,457 tests + 18 subtests; the new capture
controller's two focused tests and real initial download/resume also pass.

### V7-4 integrated runner — partial real execution

September 27: versioned integration connects retained option paths, the shared
PhysicalLedger, stock quotes, reported settlement and final action inputs.
The real five-path ledger completes DIS/ABBV and retains NVDA at its exact next
quote gap. One actual capture/resume advances the ledger with unchanged prior
cash/fills/decisions. 56 focused checks pass. Full-universe execution and real
physical outcomes remain open; this is not a full V7-4 completion receipt.
[Integration and continuation](docs/reviews/2026-09-27-v7-integrated-execution.md).

### Operations and earlier generations

- The September 5–6 audit repairs and expanded V6 pipeline were completed.
  V6's three-fold/40-member training and frozen paper activation are historical
  completed work. The abandoned local short-DTE build is not an active queue.
- V5 remains the server expert; the existing V6 paper runtime remains separate
  from the fresh Alpaca account. Retired v3/v31/v4 server artifacts were archived;
  the old EOD panel and stale monitoring were removed. Stonks publishing repairs
  and the corrected V6 broker projection were completed.
- Fresh Alpaca credentials/account isolation and the guarded V6 bridge core are
  implemented. Submissions remain disabled pending prospective integration.
- V5/V6 nightly incubator capture, sealed replay, actual September 24 full-day
  activation, timer and V6 exact-outcome exporter are implemented. Replay ran
  8,190 V5 and 5,085 V6 predictions under isolation. Ongoing health and outcome
  scoring remain in TODO; the service is not awaiting its original activation.

See [incubator activation](docs/reviews/2026-09-25-incubator-nightly-activation.md)
and [Alpaca bridge](docs/reviews/2026-09-25-v6-alpaca-order-bridge.md).

## Deferred work — not additional V7 launch prerequisites

Preserve external Pine parity, wider expert/panel research, dashboard/journal
extensions, deeper SPX0/liquidity studies, volatility/regime models, stacking and
RL sizing for their own gates. New complexity must beat its baseline before
promotion. FA automation, PIT cohorts and overlays have their own
[roadmap](fa/FA_NOTES/FA_ROADMAP.md). The October 2 Massive subscription decision,
Alpaca prospective integration and incubator monitoring retain their explicit
TODO entries. Reassess the GOALS scorecard from real forward evidence.

## Standing rules

- Point-in-time inputs, explicit availability and immutable source-bound freezes.
- Resume checkpoints with source verification; record failures instead of hiding them.
- Funded shared-capital evaluation with costs, complete accounting and causal marks.
- Preserve all declared comparisons; do not manufacture a fresh untouched holdout.
- Experts deploy alongside existing seats only after their own gates pass.
- Completed evidence stays completed unless a specific new defect invalidates it.
  Old text or an obsolete checker flag is not such a defect.

## Historical records

The former mixed chronology and completed TODO entries are preserved verbatim
in [prior ROADMAP](handoff-history/ROADMAP-2026-09-27-before-live-doc-reconciliation.md)
and [prior TODO](handoff-history/TODO-2026-09-27-before-live-doc-reconciliation.md).
Those files are historical, not competing task lists. Earlier decisions and
verdicts remain in [DECISIONS](docs/DECISIONS.md), [EXPERIMENTS](docs/EXPERIMENTS.md)
and [v3.1 history](docs/v31_run_history.md). Frozen design specs and dated reviews
are reference evidence; current instructions are exclusively TODO and HANDOFF.
