# ETFE bounded option execution component — October 5, 2026

**ETFE-3.execution-components is complete within synthetic mechanics scope.**
Full ETFE-3 execution, real-data admission and freeze/train readiness remain open.
No market downloads, training, orders or deployment were performed.

The new option ledger implements funded whole-contract entry, 0–5 DTE/timing
guards, shared 1% bar capacity, 10%-equity allocation, missing-mark guards,
partial exits with latched premium stops, fees/slippage and dated T+1 option
cash settlement. It preserves unknown references, unsupported expiry liability
and boundary outcomes. Real inputs are rejected by this component's interface.
[Bounded contract and exclusions](../specs/ETFE_EXECUTION_COMPONENTS_20261005.md).

## Hand reconciliation

| Event | Quantity / VWAP | Cash effect | Settled cash |
| --- | --- | --- | --- |
| Buy | 10 / $2.00 | Debit $2,003.00 | $97,997.00 |
| Gap stop, volume 400 | Sell 4 / $1.70 | Receivable $678.98 | $97,997.00 |
| Same-bar retry | No remaining capacity | None | $97,997.00 |
| Recovery, stop stays latched | Sell 6 / $2.10 | Receivable $1,258.11 | $97,997.00 |
| Next dated settlement clock | No remaining position | Settle $1,937.09 | $99,934.09 |

The $65.91 loss is a **synthetic arithmetic result**, not measured strategy
performance. Cashflows, quantities, fees, slippage, rounding residuals and
shared capacity reconcile independently using Decimal arithmetic. Uninterrupted
replay matches every saved prefix. A process stopped after the second event;
a fresh process restored the partial position and completed events three–five,
preserving both earlier checkpoint files byte-for-byte.

## Validation and evidence

`./venv/bin/python -m pytest tests/test_etfe_*.py -q`: **234 passed**, including
24 execution checks; two existing protobuf deprecation warnings. Tests cover
manual arithmetic, size and capacity, deterministic competing entries, no top-up,
no-trade versus missing coverage, deadlines, invalid/newer bars, stale marks and
recovery, 0/5/6 DTE, early-close cutoff, missing settlement, boundary handling,
source-bound restore, malformed-frame rollback and checkpoint corruption.

Selected root: `nn_meta/validation/etfe-execution-components-20261005-r0/`.
PLAN binds eleven source/contract/fixture files. Five checkpoints each have a
hash receipt; COMPLETE, RESUME-2-5 and INDEPENDENT_AUDIT retain the actual result.
[Machine receipt](2026-10-05-etfe-execution-components.json) and
[evidence ZIP](2026-10-05-etfe-execution-components-evidence.zip) preserve this
small study and its source snapshots. Prior ETFE consumers/artifacts are intact.

## Remaining path to freeze/train

Next component: quote-based expiry classification, OTM rolls and reservation
budgets, funded physical exercise/delivery and stock liquidation. Add the
historical settlement transition, funding failures, label horizons and full
stress cases, then reconcile admitted real paths in the integrated pilot.
Input admission/full coverage and phase-B/C demand/resource budgets remain
separate requirements. Integrated recovery and the full dataset build must
precede independently verified dataset/experiment freeze and training.
