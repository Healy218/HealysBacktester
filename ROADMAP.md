# Roadmap — expert panel and corrected research

Long-term maturity targets and the first-week v6 review are in [GOALS](GOALS.md).
Continue this roadmap toward ≥7/10 in every assessment area by December 31, 2026.

## September 25 V7-2 catalog audit checkpoint

The 591-security 5/15/30-minute catalog finished and passed its full 1,773-store
deep audit, including narrow historical-loader equivalence and the disk reserve.
The sealed stores remain validation-only. Full-scope joined daily/market context
is still missing, so 7-2 stays open and V7-3 has not started. See
[the deep audit](docs/reviews/2026-09-25-v7-2-deep-audit.md).

## September 24 incubator and V7 checkpoint

The read-only V5/V6 incubator now has a curated executable registry, sealed
generation-specific feature inputs, bounded replay/receipts and a disabled
after-close service. V6's closed-position exporter found 14 paper outcomes,
but only one exact match to the 304-row 2026-09-22 candidate day; 303 remain
pending, so there is no performance verdict. The existing V5-only server branch
received a narrow candidate-capture backport and cron opt-in without merging
divergent `main` or touching retired model-file deletions. Nine live V5 passes
sealed 3,555 distinct candidate identities by 15:47 UTC on September 24;
full-day verification, approved staging and V5 outcome joins remain open.

V7-2 remains the sole active research gate: the 591-security, 1,773-store
5/15/30 catalog is still building. Read-only preflight and resource sampling
are available, but the full catalog/source/resource audit is post-seal. Neither
V7-3 capture nor incubator production execution is authorized. See
[TODO](TODO.md), [incubator contract](docs/specs/AI_INCUBATOR.md), and the
[V5 deployment record](docs/reviews/2026-09-24-v5-capture-deployment.md).

## September 18 direction: finish V7 through items 7-1 to 7-7

The user adopted the numbered V7 sequence formerly recorded as section 6 of the
[three-day progress report](docs/reviews/2026-09-17-three-day-goals-and-progress.md)
as the ordered completion plan. [TODO](TODO.md) is the single active checklist;
[HANDOFF](HANDOFF.md) names the current item and its next concrete work.
**7-1 is complete. Before 7-2, repair and verify the deployed live V6 system on
the server, which is producing recurring errors. Then 7-2 is the current item:
causal daily/market context and feature stores.** Item 7-1
is closed under its explicit conservative admission policy; finish and document
each later item before the handoff advances again. V6 means only the deployed
server model and its live operation; the abandoned local short-DTE research
build is not part of the V7 roadmap.
The report's review pause is superseded by this staged workflow; the historical
checkpoints below are not parallel instructions to restart old workstreams.

September 18: the [dividend portion is complete](docs/reviews/2026-09-18-v7-dividends-complete.md),
with 4,918 dated payments, 4,854 verified price boundaries and no remaining cash
groups. The remaining 7-1 noncash records now have explicit source-bound
boundary exclusions consumed by the history and held-position guards; no
successor, deliverable, or cash outcome is inferred. This closes 7-1 under the
recorded admission policy and does not authorize training.

The sequence is identity/actions → causal context/features → actual option-path
capture → integrated execution → full assembly/trials → measured resource and
recovery feasibility → complete readiness. Dependencies may require touching a
later component to prove the current item, but do not open another independent
campaign or declare a later item complete prematurely.

### Completed work and evidence retained

Current 7-1 progress: the [ordinary-action admission review](docs/reviews/2026-09-17-v7-ordinary-action-admission.md)
records the user's effective-session reconstruction policy, 4,410 reconstructed
events plus 19 retained publication-reviewed events, and real consumer checks.
The subsequent [share-class review](docs/reviews/2026-09-17-v7-share-class-identities.md)
resolves 27 exact identity dates, reduces eligible mismatches to 162 and admits
four additional splits, bringing that compiled action set to 4,433 events.
The subsequent [coverage and targeted-repair work](docs/reviews/2026-09-17-v7-action-coverage.md)
implements the user-approved no-event completeness assumption, separates 45
unrelated ticker-reuse groups and admits another 48 cash events after named
GAP and process-date-tail captures. That milestone compiled 4,481 events.
[Seven finite rename reviews](docs/reviews/2026-09-17-v7-common-share-renames.md)
then clear 5,644 more history sessions and add effective-time stock-symbol
treatment, while retaining separate option-deliverable gates.
[Three unrelated rename treatments](docs/reviews/2026-09-17-v7-unrelated-renames.md)
raise admitted history coverage to 586,830 sessions.
The [authorized stock-cash ledger](docs/reviews/2026-09-17-v7-stock-cash-ledger.md)
compiles 4,337 entitlements, retains receivables separately from spendable cash
and verifies a funded captured AAPL purchase against the reviewed 2022 settlement
calendar. Remaining settlement years and 55 excluded cash events stay open.
[Ten finite split reviews](docs/reviews/2026-09-17-v7-reviewed-splits.md) now bring
the totals to 4,491 actions and 586,840 admitted history sessions. Actual feature
boundaries and funded TSLA stock accounting/mark checks pass; open-option split
transitions still require exact deliverable evidence.
The [cash/calendar continuation](docs/reviews/2026-09-17-v7-cash-calendar-closure.md)
adds 36 reviewed FCX/SLB events and entitlements: 4,527 price actions, 4,373
cash entitlements, 586,876 admitted history sessions. The original captured
Alpaca settlement-date fields resolve the later settlement schedule through
October 2026 without another market-data download. The user accepted the finite
cash-model extension for the original 528 remaining groups as each passes
review; 492 remain (437 price-action groups and 55 cash-date cases).
This advances action compilation; it does not close identity, complex-action,
no-event or held-position requirements.

The [September 18 recovery](docs/reviews/2026-09-18-v7-cash-date-recovery.md)
resolves 48 of those 55 cash-date cases and verifies all 4,421 entitlements.
At that historical checkpoint, remaining dividend review was 437 uncompiled groups plus seven date cases (444); the final dividend census supersedes it.
The finite January 2025 closed-record-date exception is source-bound; full
identity/action and held-lifecycle requirements still kept item 7-1 open at that
historical checkpoint; the explicit noncash boundary closure now supersedes it.

Use report sections 2–4 as the September 15–17 evidence index instead of repeating
all completed checkboxes here. They record base stock/options acquisition;
historical membership, identity/action inventories, raw daily/surface/sector
stores; strategy and 222-column feature components; real compact AAPL proposals
and selected-contract demand; execution, fold and trial components; and the
V6 midpoint/risk amendment. Each entry distinguishes full-scope completion from
component code and selected-data checks. The latest assembly connection and its
tests remain uncommitted implementation; it has not produced a full real dataset.

**V7 is not ready to train.** No full dataset or trained V7 model exists. The
saved gate still has eight substantive stages unpassed. The scope, source rules
and resource limits remain unchanged; progress counts only against TODO's
explicit closure evidence. This documentation reorganization completes no gate.

### Deferred work preserved outside the V7 sequence

V6's unresolved fresh-quote/health and alert-delivery behavior is recorded in
report section 4; preserve paper monitoring without silently changing policy.
Other retained backlog: dashboard/publisher and evidence-journal deployment;
external Pine parity; wider expert/panel and broker-paper rollout; prospective
FA/PIT cohorts and overlays; extra volatility/model/SPX0/stacking research; and
the GOALS first-week/year-end assessment. These are not new V7 prerequisites.
Detailed former tasks and completed checkboxes remain in the
[archived TODO](handoff-history/TODO-2026-09-17-before-report-sequence.md).
Do not infer current runtime health or authorization from older dated entries.

## Historical roadmap and acceptance criteria

The following dated phases preserve prior decisions and evidence. Current work
order is exclusively the seven-item checklist above and its current handoff.

Reconciled September 6, 2026. [TODO](TODO.md) is the active checklist;
[HANDOFF](HANDOFF.md) records session milestones. The user authorized starting
its six workstreams. Thirteen selected TradingView ports are implemented
locally and wired into an expanded, versioned research path; actual capture
admission and historical tick coverage remain gated. Work remains on `main` in the primary checkout.

The user explicitly confirmed that the **full v6 freeze/build must contain all
thirteen new indicator scopes plus quote/trade features**. The preserved
SPY/IBKR pilot validated the repaired core only; it is not authorization to scale
an existing-family-only campaign as the full v6 rebuild.

## September 14 historical phase: forward paper operation and separate short-DTE research

The expanded freeze/build and repaired three-fold/40-member training completed.
Frozen V6 experimental paper alerts are active: home calculation/portfolio,
server delivery and watcher, with the explicitly authorized 15-minute expiry
cutoff. Model weights and selection/risk rules remain frozen. The separate
**actual 1–9-calendar-day expiry** research build was abandoned before
completion; its paused 21/449 local artifact was deleted. It is not the
deployed V6 system. The user expanded V7 scope to minute option execution and
all strategy variations across 1/5/15/30-minute signals. V7 now uses March 15,
2022 through September 14, 2026;
the user superseded the initial plan to keep V6 dates. Complete [new-version preparation](docs/specs/MULTITIMEFRAME_RESEARCH.md)
before a new freeze/build/training launch. No new trained model exists yet. See
[HANDOFF](HANDOFF.md), [activation](docs/reviews/2026-09-14-v6-forward-activation.md)
and [short-DTE design](docs/specs/V6_SHORT_DTE_EXPERIMENT.md).

External Pine parity, full historical execution-quote/roll revalidation,
sustained forward evidence and dashboard portfolio integration remain open.
Training must coexist with the active home producer under a measured combined
resource budget. The first operational-week review starts September 14.

The September 6 phase descriptions below are retained as the original roadmap
and acceptance criteria, not instructions to rerun the completed V6 campaign.

## September 6 foundation (historical phase record)

The audit's 51 findings and four additional concerns are repaired and merged.
The final expanded integration suite passed **1,390 tests and 18 subtests**.
[Expanded milestone](docs/reviews/2026-09-06-expanded-v6-milestone.md) records
the final source validation and current admission boundaries.
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

## Original phase: real TradingView validation and expanded tick coverage

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
review. Replacement `raw-options-20260906-r2` completed both freezes and IBKR rows;
its remaining SPY build was stopped before expanded integration. It did not complete assembly.
Its two-worker core campaign and nonzero stop status are preserved; its
recovery descriptor is retired. Expanded v6 needs a new campaign.
[Restoration evidence](docs/reviews/2026-09-06-pilot-cache-restoration.json).

In parallel: inventory deeper backups and missing FA/PIT monthlies; preserve
the 211/441 historical v6 partials; verify server readiness; advance independent
resolver/FA automation. Fresh campaign paths and guarded launchers are implemented.

The continuation adds historical option quotes/trades and reuse of the existing
server sockets to the v6/v7 scope. A predecision-selected tick sample
now materializes all ten features and exact joins. Full historical model rows
and training remain pending. Fixed contract selection is shared with labels;
historical/live feature parity and ablations precede
any predictive-gain claim. Existing 15-minute closed-bar decisions remain the
initial near-live target.

**Exit:** retain the verified core-pilot evidence, complete actual all-source
comparisons/context and full required tick coverage, then seal the expanded
input contract and validate the fresh launch. Each new TradingView scope
requires reviewed rules and external parity evidence. v6's existing window stays equal to v5's; the archive audit found
fifteen weekly-expiry names.

## Original next phase: corrected baseline and expanded-pool evidence

Refreeze expanded v6 under `2026-09-06-tv13-option-ticks-v4` after the
[sealed feature input gates](docs/specs/V6_EXPANDED_INPUTS.md); core pools remain
under `2026-09-06-raw-spot-v3`. Rebuild rows and complete marks, retain
provenance and assemble with PIT membership. Pre-audit v5 rows
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
| AI artifact incubator | V5/V6 replay, sealed feature routing and receipts implemented; V5 scanner capture live; after-close execution disabled | Complete-day V5 validation, approved paper-data staging and exact outcomes; V7 admission only after 7-2–7-7 |
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
