# Handoff — September 28, 2026 — V6 independent paper orders deployed

## Focus and stopping point

V6 paper readiness was restored, then the user approved two-minute order waits,
±2% midpoint limits and independent order processing. V2 deployed at 12:01
Central; authenticated preview and polling passed. No actual V2 fill has been
observed at this checkpoint. Next selected work remains gate 7-3.
[Policy/evidence](docs/reviews/2026-09-28-v6-independent-orders.md).

## Completed and preserved

- New buys: midpoint × 1.02 rounded up to cents; sells: × 0.98 rounded down.
  Price stays fixed; cancellation begins at 120 seconds. Fill is not guaranteed.
- Unrelated broker orders proceed independently; each POST is journaled and
  reconciled. Same-contract/position dependencies, pending-buy cash reservations,
  partial holdings and ambiguous-response protections remain enforced.
- New bridge/pricing/dispatcher files are hash-bound alongside original sources.
  Prior manifest/service preserved at the paper state's
  `runtime-revisions/orders-v2-20260928/`. Activation/account/journal unchanged.
- Forty-five focused tests and systemd validation passed. Real service/timer
  verified; preflight had no holdings or pending orders. Observe live receipts
  for subsequent state rather than treating this snapshot as present health.
- Earlier readiness repair published immutable restated-price inputs, retained
  the frozen model and selected scanner v3 (up to eight workers / 12 GiB).
  A full scan took 243.058 seconds; an original-policy order was accepted,
  canceled unfilled and reconciled. [Repair](docs/reviews/2026-09-28-v6-paper-readiness.md).
- V7 entry download completed at 04:58; V6 catch-up resumed at 05:00 but was
  stopped for paper hours. A calendar guard now rejects intraday research starts.

## Next actions

1. Read TODO, then use [CURRENT_STATE](docs/CURRENT_STATE.md) for exact pointers.
   Do not repeat activation, reset journals or rebind old source/artifact hashes.
2. Return to 7-3 references, actual held/exit/roll/stock gaps and reconciliation.
   Preserve partial 7-4 ledgers; entry capture is complete. Do not rebuild the
   catalog, daily data, demand census or completed packing trial.
3. Observe actual prospective V2 fills and sustained reconciliation. Tests and
   successful startup do not establish fill quality or model performance.
4. Incubator r1 requires compatible/new input-lineage review after provider
   restatements, then catch-up/freeze/training. Checkpoints are preserved;
   full nightly latency and an updated model remain unproven.
5. Retain the October 2 provider decision and existing FA collection schedules.

## Constraints

Preserve unrelated dirty/untracked work. Research, operational models and paper
state remain isolated. Model promotion requires its own admission. Full-scope
validation, deployment and measured outcomes are distinct. Selected operating
policy is versioned; historical narratives are not live configuration.
