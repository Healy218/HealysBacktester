# ETFE expiry and physical delivery — October 5, 2026

**ETFE-3.expiry-components is complete within bounded synthetic scope.**
This continues a verified option-prefix snapshot without modifying its source
or artifact identity. Full execution validation, real input admission, labels
and dataset freeze remain open. No market capture, training, orders or deployment.
[Component contract](../specs/ETFE_EXPIRY_COMPONENTS_20261005.md).

Implemented quote-based expiry classification, latched exits and OTM rolls,
shared cash/share reservations, official-reference exercise/nonexercise,
dated option/equity settlement, call stock delivery and partial bid liquidation.
Adjusted integer-share/cash deliverables require an explicit exercise basis;
unresolved fractional deliverables stay blocked. Every purchase remains 0–5 DTE.

## Hand cases and independent reconciliation

| Synthetic case | Result | Evidence boundary |
| --- | --- | --- |
| Funded call | Three contracts cost $600.90; $60,000 exercise debit reserved. 300 shares arrive May 29. Sales of 100 at $210 and 200 at $211 net $20,968.50 and $42,136.70. Final settled cash May 30: **$102,504.30**. | Arithmetic only; the $2,504.30 gain is not observed strategy performance. |
| Unfunded put | $99,399.10 cash remains; three option contracts retain `funding_unresolved`. | No owned shares, no manufactured short position or zero-price sale. |
| Competing calls | $98,798.20 cash; QQQ's $60,000 reserve leaves **$38,798.20** available. SPY remains funding-unresolved. | Deterministic tie order and shared reservation; no future stock proceeds fund SPY. |
| Settled-proceeds roll | Old sale nets **$569.14**, available May 28. New leg buys two contracts at $200.30 each; cash **$99,567.64**, new position still open. | No terminal return label; roll budget is old settled proceeds, not a new 10% allocation. |

Independent Decimal reconciliation checks every option/stock fill, fee, slippage,
rounding residual, cash/share conservation, size limit and declared settlement
date. All **13 saved prefixes** match uninterrupted replay. A process stopped
after two funded-call observations; a fresh process restored pending exercise
delivery, completed all four cases and retained both prior checkpoints unchanged.

## Validation

`./venv/bin/python -m pytest tests/test_etfe_*.py -q`: **265 passed**, including
31 new lifecycle checks; two existing protobuf deprecation warnings. Coverage
includes threshold/nonexercise, partial option exit followed by residual exercise,
funding and roll-budget competition, 0–5 DTE selection, reset stop denominator,
roll cancellation/maximum, dated early close, quote freshness/source/size guards,
missing references/terms/calendars, adjusted deliverables, $5 exercise fee,
holiday and T+2/T+1 transition, missing liquidation, boundary distinctions,
source-bound restart, unresolved-prefix rejection and checkpoint corruption.

Selected root: `nn_meta/validation/etfe-expiry-components-20261005-r0/`.
PLAN binds twelve source/spec/fixture/test files. Thirteen checkpoint/hash pairs,
COMPLETE, RESUME-2 and INDEPENDENT_AUDIT retain the actual evidence.
[Machine receipt](2026-10-05-etfe-expiry-components.json),
[full small evidence bundle](2026-10-05-etfe-expiry-components-evidence.zip).
Prior source-bound option/feature/action studies remain unchanged.

## Remaining execution and freeze gates

The continuation accepts synthetic fixtures only. Its caller owns complete event
scheduling; ordinary new entries after continuation are not integrated. Next:
shared scheduler, settlement-extended horizons, mixed-path/funded-put inventory
integration, full stress suite and recovery. Then admitted real paths in the
integrated pilot. Fresh dated inputs/full coverage, phase-B/C demand budgets,
full dataset build and independently verified freeze still precede training.
