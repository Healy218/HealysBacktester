# Handoff — first TradingView implementation and readiness batch

September 5, 2026 (Chicago; work continued September 6 UTC). All six user-authorized
workstreams have started. [TODO](TODO.md) is the active checklist;
[ROADMAP](ROADMAP.md) retains the phase gates. This is a completed first batch,
not completion of the full indicator expansion or corrected research campaign.

## Code and validation

Work remains on `main` in `/home/healy/Coding/HealysBacktester`, following the
merged audit at `d7d7816` (`79d3b58` repairs). All 51 original findings and four
additional concerns have corrective code. The pre-change rerun passed 642 tests
and 18 subtests. Final integration passed **790 tests and 18 subtests**, ten
warnings, in 23.30 seconds. Shell syntax, diff checks, source registry and the
read-only campaign preview also pass.

Contract remains `2026-09-05-causal-v2`. Preserve all pre-audit freezes, rows,
marks, bundles and untracked `nn_meta/artifacts_v6/` (old 211/441 partial run).
Do not resume those partials, relabel old files, or reuse old v5 rows.

## TradingView selection and first ports

The exact ranking covers 42 general-listing pages / 1,000 recent scripts and
32 Editors' Picks pages / 758 scripts. Use the literal supplied URLs while the
optional all-time clarification is unanswered. Ten plus three gives thirteen
unique selections. [Selection table and status](docs/specs/TRADINGVIEW_EXPANSION.md).

All thirteen exact public Pine revisions are pinned under
`indicators/tradingview_sources`, with hashes, authors, licenses and versions.
The source snapshot is historical and still describes its original capture
point; current acquisition/adaptation manifests are authoritative for progress.

Eight selections now have scoped Python implementations and local tests:
Gaussian, Fibonacci, Uptrick, RSI Probability Matrix, ICT Killzones, Emre MSB,
Support Resistance Channels and Volume-Weighted Order Blocks. Six have explicit
four-frame proposal wrappers; ICT and VWOB are feature/event-only. Emre's box
arrays are still unported. Source account dashboards do not supply option-ledger
labels; RSI's target-first ambiguity is explicit in causal reference statistics.

**None are admitted to active pools.** Exported TradingView fixtures are pending,
including flat-RSI, pivot-tie and statement-order edges. Session D/W/M features
require exact exchange boundary flags. Calculation origin must be fixed where
Pine uses `calc_bars_count`; a moving replay tail changes state initialization.

`./venv/bin/python -m indicators.tradingview_registry` validates all thirteen
sources against snapshot Pine IDs/revisions and hashes. Implemented fixture
identities bind adaptation records, code, wrappers and shared helpers. Local
formula/prefix/replay tests and source review do not establish TradingView parity.

Five implementations remain: AMD Po3, Footprint, Structural Liquidity & POC,
Setup Scanner, HTF Log-Regression Volume Profile. Footprint engines have separate
OHLCV/intrabar/native data requirements. `TradingView/ta/14` is pinned; unused
transitive `RelativeValue/3` is still documented as pending.

## Data repair and campaign preparation

A new concrete downloader defect was found and fixed: `_load_chunked` omitted
the last date of each chunk. Requests now have adjacent exclusive boundaries
and include the overall end date; six regression cases cover it.

The existing v5/v6 cache is unchanged and incomplete: 500 option dates versus
495 underlying dates within 2024-08-26 through 2026-08-24. Missing dates:
`2025-03-31`, `2025-07-31`, `2026-03-31`, `2026-07-31`, `2026-08-24`.
The old one-direction preflight passes; the new campaign launcher refuses them.

Restored 38 MiB of SPY minute history (2017–2026) from the existing GCS backup
into the previously missing raw tree. Four missing dates are present; August24
is beyond the backup's August18 end. The restored 2025 bars resample to exactly
matching OHLCV on all 6,448 overlapping cache bars. Full-universe recovery and
older year-end repairs are still open. [Recovery evidence](docs/reviews/2026-09-05-spy-restore.json).

`NN_META_CAMPAIGN` isolates artifacts/runs/reports/model_final by campaign and
pool; raw inputs remain shared. v5/v6 default final bundle paths now belong to
the selected pool. The new local launcher previews by default:

```sh
scripts/run_research_local.sh --campaign causal-tv-pilot --pool v6 --stage freeze --symbols SPY,QQQ
```

Repeat ordered `--stage` for freeze/build/assemble/evaluate/finalize. `--run`
requires two-way date coverage, named outputs, immutable input/source/runtime
fingerprints and matching resume scope. Freeze uses stable per-symbol shards
and an exact merge list; errors propagate. It does not pull old cloud specs.
No actual freeze/build/train/evaluate/finalize ran. Existing configured v5/v6
families remain unchanged; the new prototypes need admission first.

## Actual operational state

Read-only server checks found deployed commit `9351d01ee487299ae208393cfad021da0330950b`,
pre-audit. Four expert crons use documented staggering/workers. Stock and option
feed processes existed, but off-hours heartbeat values are not session parity.
No alerts, digests, orders, crons or production state were changed.

Both system and user managers report home backup/StockTwits timers absent.
The user deadman timer is active. Server FA archive/v3 cache exist; local FA
archive/full v3 cache/SPX0 history still need recovery. Do not confuse committed
systemd templates with installed jobs. [Full readiness review](docs/reviews/2026-09-05-readiness-milestone.md).

Full-session closed-bar stream/REST comparison and restart/backfill evidence
remain pending. Coordinate corrected source with rebuilt compatible bundles;
source-only deployment can stop experts because old bundles are rejected.
Server delivery stays git pull, never scp. Bracket process patterns and avoid
heartbeat/digest entrypoints during read-only work because they can notify.

## Execution and next order

A pure `nn_meta.live.contract_preview` now resolves captured complete chain
snapshots with receipt-time, quote-age, OCC, signed-delta and liquidity checks.
It preserves quote nanoseconds, refuses duplicates/future observations and emits
a concrete preview plus hashed JSON. Deliverables remain explicitly unverified:
100 reported shares does not exclude additional cash/equity deliverables.

Next: finish remaining indicator scopes and exported fixtures; recover/validate
full underlying inputs; then corrected freeze/rows/marks/PIT, conditional
walk-forward evaluation and finalization. Keep v6's v5 window; deeper v7/SPX0
research follows restored history. Complete full-session parity and coordinated
rollout. Wire contract reference/quote capture, offline selection and costed
entry/exit/roll accounting before the paper execution seat. The shared alert
format still needs the prior concrete go/no-go before production wiring.

Prospective FA/PIT automation and timer restoration remain open; the August FA
monthly counts as zero clean prospective cohorts toward the three-cohort gate.
Volatility, SPX0 reevaluation, stacking and RL remain in that dependency order.

Previous documentation milestone was archived at
[HANDOFF-2026-09-05-documentation-milestone](handoff-history/HANDOFF-2026-09-05-documentation-milestone.md).
