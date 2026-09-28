# V6 four-step paper orders — September 28, 2026

The user replaced the fixed ±2% / 120-second policy with a four-step ladder for
future paper orders. The step policy deployed at **14:52:51 Central**; authenticated preview and
the installed broker service passed. The final sell-slice adapter deployed at
**15:08:42 Central**; authenticated reconciliation passed and correctly returned
`market_closed`. Actual prospective ladder fills
remain unobserved. No test orders were manufactured for deployment verification.

## Execution policy

| Step | Buy limit | Sell limit | Wait before cancellation |
| --- | --- | --- | --- |
| 1 | Initial midpoint × 1.025 | Initial midpoint × 0.975 | 30 seconds |
| 2 | Initial midpoint × 1.05 | Initial midpoint × 0.95 | 30 seconds |
| 3 | Initial midpoint × 1.075 | Initial midpoint × 0.925 | 30 seconds |
| 4 | Initial midpoint × 1.10 | Initial midpoint × 0.90 | 60 seconds |

Buys round up and sells down to cents. All steps use the first validated
bid/ask midpoint. Each new order/replacement still validates current quotes,
displayed quantity, eligibility, cash and ownership. Marks and model risk
thresholds are unchanged. Limits may cross the current touch; fills are not
guaranteed.

Replacement uses **cancel, confirm, then submit the remaining quantity** with
a unique durable client ID. There is never an intentional overlap for the same
ladder. Alpaca's cancellation request can remain pending until the venue confirms
it, so acknowledgement is not treated as cancellation.
[Alpaca order lifecycle](https://docs.alpaca.markets/us/docs/orders-at-alpaca).

The waits total 150 seconds of configured order time. The existing 15-second
poll cadence and cancellation confirmation add latency; 150 seconds is not an
exact total wall-clock promise. Each stage waits from its own recorded plan.
A 300-second recovery ceiling stops stale chains after extended delay/restart.
The original five-minute signal deadline applies to the initial submission;
an already-admitted ladder can finish after that deadline. A crash before first
submission does not bypass the initial deadline.

Buy quantity and cash reservations use the maximum +10% price from the outset,
including cancellation gaps. Actual partial fills remain owned and only the
unfilled remainder advances. A superseding close stops an entry ladder before
selling its actual holding. Rejections, expirations and external cancellations
end that ladder; they do not silently restart it. After the last step, any
remaining order is canceled. Unfilled sell quantity remains an actual holding;
the same exhausted close event is not automatically retried indefinitely.
If a displayed-size sell slice fills completely and owned contracts remain, a
new slice may run its own bounded ladder after fresh ownership and quote checks.
This preserves complete liquidation without restarting canceled/failed ladders.

## Durable state and scanner integration

Selected implementation: `v6_bridge_v3.py`, `v6_pricing_v3.py`,
`v6_step_slices.py` and `run_v6_alpaca_runtime_v4.py`. `broker-orders.sqlite3` retains its existing
orders/observations and adds `step_chains` for ownership across steps. Intents
precede POSTs; cancellation intent precedes DELETE. Unknown submission outcomes
fail closed and reconcile by client ID. Unrelated orders continue independently.

Scanner v6 uses `v6_source_reconcile_v2.py`: an active ladder protects its source
projection even between confirmed cancellation and replacement. Completed,
expired, never-filled initial sources can still be archived under the prior
repair. Pending/uncertain orders and any prior fill remain protected.

Legacy orders keep their recorded timeout and price; old attempts do not receive
new ladders retroactively. Prior source hashes remain in the manifest. Runtime
backups (manifest, services, portfolio and journal) are under the paper state's
`runtime-revisions/step-orders-v3-20260928/` and
`runtime-revisions/step-orders-slices-20260928/`. Activation/account/model are intact.

## Validation and deployment

- Source commits: `a93b7a9` and `2d8ce52`.
- **76 focused tests passed** across ladder, legacy order, runtime, source
  reconciliation and launcher behavior. Coverage includes all steps, sell
  symmetry, partial/cancel races, unknown POSTs, restart idempotence, stale
  quotes, reservations, signal deadlines and scanner protection between steps.
- Shell syntax and installed-unit definitions passed validation.
- Cutover reconciliation: zero actual holdings and zero pending orders;
  authenticated V3 preview passed, then the installed order service exited 0.
- Policy: `midpoint-step-2.5-5-7.5-10pct-v3`.
- Scanner policy: `archive-expired-never-filled-source-v2-step-aware`.
- Current paper-manifest SHA:
  `f7467a569c5db625d480390d59dc048a66024690f73ff11ebc7ad7658a0a2898`.
- Receipts: `nn_meta/validation/v6-step-orders-20260928/deployment.json` and
  `nn_meta/validation/v6-step-orders-slices-20260928/deployment.json`.

Separately, the previous v4 scanner's 14:45 pass archived IONQ/CRM automatically
and completed in 256.738 seconds, confirming recovery after their unfilled
orders. This is evidence for the earlier repair, not a live V3 ladder trial.
Read current broker/scanner receipts for subsequent state.
