# Roadmap — expert panel and corrected research

Reconciled September 6, 2026. [TODO](TODO.md) is the active checklist;
[HANDOFF](HANDOFF.md) records session milestones. The user authorized starting
its six workstreams. Thirteen selected TradingView ports are implemented
locally; admission remains gated while the existing configured pools receive
corrected pipeline checks. Work remains on `main` in the primary checkout.

The user explicitly confirmed that the **full v6 freeze/build must contain all
thirteen new indicator scopes plus quote/trade features**. The current
SPY/IBKR run validates the repaired core only; it is not authorization to scale
an existing-family-only campaign as the full v6 rebuild.

## Current foundation

The audit's 51 findings and four additional concerns are repaired and merged.
The latest completed full suite passed **1,143 tests and 18 subtests**.
Causal features/splits, cash/mark/cost accounting, PIT selection, cache
preservation, provenance and live-state safeguards are implemented.
[Integration](docs/reviews/2026-09-05-main-integration.md) and
[migration requirements](docs/reviews/2026-09-05-remediation.md).

Other completed foundations: per-underlying chain reads and sorted new
universe derivations; v5 wide pool/PIT; PBO and magnitude/EV heads; panel
watchlists; Keltner/BBW and weekly-DTE scaffolding; streamed SIP bars, OPRA
quote storage, closed-bar freshness and REST fallback. Massive Options
Advanced and Alpaca Algo Trader Plus upgrades landed.

Read-only server inspection found pre-audit commit `9351d01`, four expert crons
and both feed processes. Source integration did not deploy this audit or
regenerate the v3/v4/v31/v5 models; full-session parity remains unverified.
Old results remain in
[EXPERIMENTS](docs/EXPERIMENTS.md) as history, including the intraday-staleness
incident and September 4 gate change.

## Current phase: TradingView validation and corrected pipeline pilot

The scope covers the user's **ten highest-boost scripts across the supplied
general listing's exposed pages plus three highest-boost Editors' Picks**.
These thirteen distinct open-source indicators are additional to Keltner/BBW,
and all have scoped local ports. The general selection is recent-library
scope, not an all-time ranking.
[Selection and acceptance plan](docs/specs/TRADINGVIEW_EXPANSION.md).

Exact sources, attribution, supported inputs and runtime identities are pinned.
The [fixture capture/comparison workflow](docs/specs/TRADINGVIEW_FIXTURE_RUNBOOK.md)
is implemented; actual external chart fixtures and admission remain open.
Confirmed structure, sessions, statistics, profiles and footprint modes retain
explicit knowledge times and scope limits. Admit calculations after Pine parity,
causal prefix tests, batch/incremental equivalence and matching live/offline
semantics. Unsupported footprint/intrabar modes remain pending.

The corrected data candidate is complete: **453 stocks** with **6,887,003
timestamps shared exactly by the fresh raw and all-adjusted panels**; 602 stock
sessions including warmup and 500 baseline sessions pass coverage with explicit
issuer/no-trade exceptions. The **5,214,222-contract all-observed universe** and
500 option day files are retained. Raw-spot filtering rederived **33,597,149
option daily rows** and 266,905 surface rows. Original cache bytes are preserved;
the calendar extends through December 2027.
[Sealed data evidence](docs/reviews/2026-09-06-data-repair.json).

The first SPY/IBKR pilot, `raw-options-20260906`, exposed provider writes into
the sealed candidate and was aborted. All 123,471 sealed payload hashes were
verified; 1,299 derived files were preserved in campaign quarantine and the
exact original inventory/seal restored. Its IBKR shard is preserved as
ineligible history. The separate writable provider-cache fix passed independent
review. Replacement `raw-options-20260906-r2` is running freeze/build/assemble
with two dynamically selected workers; complete it before scaling.
[Restoration evidence](docs/reviews/2026-09-06-pilot-cache-restoration.json).

In parallel: inventory deeper backups and missing FA/PIT monthlies; preserve
the 211/441 historical v6 partials; verify server readiness; advance independent
resolver/FA automation. Fresh campaign paths and guarded launchers are implemented.

The continuation adds historical option quotes/trades and reuse of the existing
server sockets to the v6/v7 scope. Bounded tick capture and descriptive causal
replay are verified, but ticks have not been joined to model rows or trained.
Fixed contract selection, historical/live feature parity and ablations precede
any predictive-gain claim. Existing 15-minute closed-bar decisions remain the
initial near-live target.

**Exit:** the configured-pool pilot completes with unchanged sealed inputs;
generation/source contracts and launch commands are validated. Each new
TradingView admission separately requires reviewed rules and external parity
evidence. v6's existing window stays equal to v5's; the archive audit found
fifteen weekly-expiry names.

## Next phase: corrected baseline and expanded-pool evidence

Refreeze affected pools under `2026-09-06-raw-spot-v3`, rebuild rows and complete
marks, retain provenance and assemble with PIT membership. Pre-audit v5 rows
and paused v6 shards cannot seed this campaign. Use the home box first;
cloud is measured acceleration with VM-hour budgets and job-bound monitoring,
not a guaranteed spending cap.

Evaluate baseline and expanded candidates on identical corrected inputs and
cash/cost ledgers. Globally optimized proposals require later validation/test;
report conditional selection. End-to-end nesting requires fold-local
refreezing. Check reproducibility, costs, ex-outliers, calibration,
PBO/deflated Sharpe and effective gate settings.

**Exit:** corrected results/refusals are recorded; passing bundles verify
against exact source/row/mark fingerprints and pass isolated previews.
Prepare coordinated rollout after compatibility and full-session readiness
checks. Future effectiveness claims need fresh forward evidence.

## Panel growth and execution dependencies

| Workstream | Current position | Next gate |
|---|---|---|
| Classification/meta-selection | Models, calibration, PBO and EV implemented | Corrected baseline/expanded evidence and prospective panel record |
| Contracts/quotes and paper execution | Feed stores implemented; resolver/sizing/reconciliation remain | Contract/quote plumbing and offline twin before paper orders |
| v7 real-time/deeper history | Upgrades landed; [REALTIME_SPEC](docs/specs/REALTIME_SPEC.md) preserved | Historical/live parity, deeper PIT/surface coverage and a fixed window |
| SPX0 | Bounded verticals and package accounting implemented; four rounds established no seat | Corrected deeper-regime evidence, liquidity/cost checks and 25% DD gate |
| Volatility | HAR-RV/GARCH machinery exists | Available-at features and sequence-model improvement per regime |
| FA discovery | Collectors, ranker and forward tracker implemented | Automation/digest/overlays and three clean forward-tracked monthlies |
| Stacked blend | Queued behind validated experts and FA | Improve panel OOS/forward evidence |
| RL sizing/exits | Last | Reliable execution ledger and improvement over simple sizing |

Quote-verified accounting and Alpaca paper execution remain separate from the
implemented OHLCV ledger and alert experts. Shared alert-format go/no-go
applies to a concrete preview. DD-braked alert bundles remain refused while
the scanner lacks policy-enforcing sizing.

Option ticks now have a bounded historical downloader, verified descriptive
causal replay and an opt-in socket journal. The two-contract pilot establishes
access and capture; complete training coverage and model joins remain open.
Fixed pre-decision contract
selection, trade-condition mapping, historical/live feature parity and costed
evaluation precede model admission. Full-session server evidence is still open.

FA's contaminated August monthly is historical, not a clean prospective cohort.
Automate immutable captures and PIT maintenance on the home box in parallel;
collectors must keep accumulating future evidence. Underlying watchlist rates
describe entry cohorts, not realized option P&L.

## Standing rules

- Point-in-time inputs, explicit availability, frozen artifacts, no retroactive
  edits or relabeled provenance.
- Checkpoint long stages with input verification and visible failures.
- Portfolio-level OOS with funded positions, complete costs and marks.
- New complexity must beat the boring baseline before promotion.
- Experts join alongside existing seats with their own state/ledgers;
  promotion follows verified gates and forward evidence.
- Preserve decisions and failed experiments; changed criteria do not create
  a fresh untouched holdout.

History: [archived roadmap](handoff-history/ROADMAP-2026-09-05-before-checklist-reconciliation.md),
[EXPERIMENTS](docs/EXPERIMENTS.md), [DECISIONS](docs/DECISIONS.md),
[v3.1 history](docs/v31_run_history.md).
