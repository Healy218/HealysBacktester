# Roadmap — expert panel and corrected research

Reconciled September 5, 2026. [TODO](TODO.md) is the active checklist;
[HANDOFF](HANDOFF.md) records session milestones. The user authorized starting
its six workstreams, with TradingView integration before corrected research
rebuilds. Work remains on `main` in the primary checkout.

## Current foundation

The audit's 51 findings and four additional concerns are repaired and merged.
Integration and the planning rerun passed **642 tests and 18 subtests**.
Causal features/splits, cash/mark/cost accounting, PIT selection, cache
preservation, provenance and live-state safeguards are implemented.
[Integration](docs/reviews/2026-09-05-main-integration.md) and
[migration requirements](docs/reviews/2026-09-05-remediation.md).

Other completed foundations: per-underlying chain reads and sorted new
universe derivations; v5 wide pool/PIT; PBO and magnitude/EV heads; panel
watchlists; Keltner/BBW and weekly-DTE scaffolding; streamed SIP bars, OPRA
quote storage, closed-bar freshness and REST fallback. Massive Options
Advanced and Alpaca Algo Trader Plus upgrades landed.

Last deployment notes report v3, v4, v31 and v5 alert experts. Source integration
did not deploy this audit or regenerate their models. Deployed state and
full-session parity need current verification. Old results remain in
[EXPERIMENTS](docs/EXPERIMENTS.md) as history, including the intraday-staleness
incident and September 4 gate change.

## Current phase: TradingView and campaign readiness

Implement the user's **ten highest-boost scripts across the supplied general
listing's exposed pages plus three highest-boost Editors' Picks**. Thirteen
distinct open-source indicators are additional to Keltner/BBW. The general
selection is recent-library scope, not an all-time ranking.
[Selection and acceptance plan](docs/specs/TRADINGVIEW_EXPANSION.md).

Pin sources/attribution and mechanical rules before porting. Confirmed
structure, sessions, statistics, profiles and footprint modes need explicit
knowledge times. Admit calculations after Pine parity, causal prefix tests,
batch/incremental equivalence and matching live/offline semantics. Keep
unsupported modes visibly pending.

In parallel: reconcile raw caches/backups and coverage; preserve the 211/441
historical v6 partials; create fresh campaign paths/launchers; inspect server
readiness; advance independent resolver/FA automation.

**Exit:** admitted calculations have reviewed rules and parity evidence;
generation/source contracts are fixed; corrected inputs and launch commands
are preflighted. v6's existing window stays equal to v5's; the archive audit
found fifteen weekly-expiry names.

## Next phase: corrected baseline and expanded-pool evidence

Refreeze affected pools under `2026-09-05-causal-v2`, rebuild rows and complete
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
