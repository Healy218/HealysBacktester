# Handoff — September 28, 2026 — V6 step orders deployed

## Focus and stopping point

The user requested four-step buy/sell orders after the never-filled-source repair.
The policy deployed at 14:52 Central; its final sell-slice adapter deployed at
15:08. Authenticated checks passed; the market was closed at the final check.
No prospective step-order chain has run yet. V7 gate 7-3 remains selected, with
reference acquisition continuing independently.

## Changes and evidence

- Buy limits: initial midpoint × 1.025/1.05/1.075/1.10; sell limits:
  × .975/.95/.925/.90. Waits are 30/30/30/60 seconds, then cancel. Buys round up,
  sells down to cents. Polling/cancel confirmation add wall-clock latency.
- Cancel confirmation precedes replacement of only the unfilled remainder.
  Initial midpoint stays fixed; fresh quote/eligibility checks still apply.
  Buy sizing/reservations use the maximum step, including cancellation gaps.
- Independent orders, pending/partial/unknown-state protections remain. New
  step_chains journal state makes restarts and scanner protection explicit.
  Legacy orders keep their original policy; exhausted ladders do not restart.
- Successful displayed-size sell slices can continue closing real remaining
  holdings through their own bounded ladders. Failed/canceled slices cannot
  silently restart. A failed final sell leaves its actual residual holding.
- New sources preserve all old source hashes and model/activation lineage.
  Runtime is run_v6_alpaca_runtime_v4; scanner adapter is scanner_v6. Exact
  manifest, backups and service pointers are in CURRENT_STATE.
- 76 focused tests, shell and systemd checks passed. Final authenticated state:
  zero holdings/pending orders, six legacy canceled orders, zero step chains.
  [Policy/deployment evidence](docs/reviews/2026-09-28-v6-step-orders.md).
- The earlier scanner repair was observed prospectively: the 14:45 scan archived
  IONQ/CRM automatically after their zero-fill cancellations and completed in
  256.738 seconds. It no longer stalled on those simulated projections.

## Next actions

1. Observe prospective step-order fills/cancellations and subsequent scans.
   Tests and successful deployment are not measured fill quality or profitability.
2. Continue 7-3 references, failure census/admission and actual held/exit/roll/stock
   discovery. Entry capture is complete; do not restart it or broaden the five
   exact blackouts. Read current reference progress rather than old counters.
3. Preserve the five-case execution frontier and integrated ledger ending in
   20260928-r1; full-universe discovery remains distinct and incomplete.
4. Incubator catch-up still needs compatible input-lineage review and full daily
   freeze/training proof. Preserve checkpoints and the paper-hours research guard.
5. Keep the October 2 provider decision and existing FA schedules.

## Constraints

Preserve unrelated dirty/untracked work. Never relabel frozen producers. Paper,
research and operational models remain isolated. The scanner's broader simulated
position/roll lifecycle is not yet a fully broker-native implementation.
