# ETFE shared scheduler and stress matrix — October 5, 2026

**ETFE-3.integration-components is complete within bounded synthetic scope.**
Ordinary entries and expiry/roll/physical delivery now share cash, participation,
slots, observation clocks and settlement-extended diagnostic horizons.
Scientific labels, real-source admission and full-history execution remain open.
No market capture, training, orders or deployment occurred.
[Component contract](../specs/ETFE_INTEGRATION_COMPONENTS_20261005.md).

## Bounded result

Six immutable tapes run against **27 profiles**, producing **162 complete
case/profile results and 189 proposal outcomes** (the mixed tape has two paths).
Profiles include every declared isolated cost, lag, participation, minimum
activity, bar-removal and exercise-fee stress plus the combined conservative case.
Miniature thirty-minute sessions make clocks inspectable; they do not reproduce
real exchange-hour diversity or whole-history stress performance.

| Baseline synthetic tape | Ending cash | Outcome |
| --- | --- | --- |
| Ordinary round trip | $100,093.85 | Settled May 28 at 09:30 New York; option sold May 24 |
| Shared SPY/QQQ paths | $100,187.70 | Two settled paths, deterministic entry order |
| Funded call / stock sale | $102,304.60 | Settled May 30 at 09:30 New York; horizon includes stock cash settlement |
| Settled-proceeds roll | $99,567.64 | Two contracts in new leg, still open |
| Unfunded put | $99,399.10 | Funding unresolved; no invented shares |
| Fixed-end round trip | $97,997.00 | Sale proceeds unsettled at fixed end; right-censored |

These cash differences are hand-worked synthetic arithmetic, not measured
strategy returns. Across all profiles the census is: **95 settled, 24 observed
unfilled, 20 open, 3 input-unresolved, 23 funding-unresolved and 24 right-censored**.
Every model target stays null and every training-admission flag stays false.

The three input-unresolved paths are informative acquisition requirements:
the 0.5% participation roll needs a later selection quote after an unaffordable
attempt; two edge-block removals prevent the old option sale and require an
official exercise reference absent from that roll tape. These paths remain in
the census and are not converted to losses, empty markets or boundary censoring.

## Verification and recovery

**289 focused ETFE tests pass**, including 24 new integration checks; two existing
protobuf deprecation warnings. Tests cover generated entry/deadline clocks,
settlement priority, mixed symbols, all-leg stressed costs, participation,
availability lag, missing coverage/terms, no-trade, causal prefix invariance,
consecutive roll windows, delayed official reference, stock terminal horizons,
fixed-end liabilities, complete stress grid and corrupted restart evidence.

A process stopped after event 20. A fresh process restored its immutable state
and finished all 162 combinations, preserving the checkpoint bytes. The audit
replayed that prefix and every final state/report, independently reconciling
Decimal costs/rounding, cash/share/contract conservation, participation,
reservations, all six manual baselines and census/null-target completeness.
Missing receipt publication is separately tested: deterministic replay must
match the payload before a receipt can be recovered.

Selected root: `nn_meta/validation/etfe-integration-components-20261005-r0/`.
PLAN binds thirteen source/spec/fixture/test files. Hashed results, checkpoint,
COMPLETE, RESUME-1 and INDEPENDENT_AUDIT are retained in the
[machine receipt](2026-10-05-etfe-integration-components.json) and
[evidence bundle](2026-10-05-etfe-integration-components-evidence.zip).
Both previous source-bound execution studies remain unchanged.

## Next selected work and remaining gates

**ETFE-1.demand:** finish full phase-B/C acquisition demand and measured budgets,
including holding/roll/exercise/stock paths and conditional stress demand.
Resolve the dated provider inputs necessary for real execution, then integrate
fresh capture/features/execution/isolated labels in ETFE-4.pilot with resource
and recovery measurements. Full-history build, temporal validation rules and
independently verified dataset/experiment freeze still precede training.
Revision sensitivity remains unmeasured without vintage pairs. The cash-only,
single-underlying baseline provides no admitted funded-put inventory path.
