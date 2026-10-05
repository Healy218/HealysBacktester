# Handoff — October 4, 2026 — Pilot trade windows captured

## Focus and completed result

Continued fresh Alpaca-only ETFE, 0–5 DTE including signal-qualified 0DTE.
Completed **ETFE-1.trade-window-capture**, the next bounded acquisition step.
[Review](docs/reviews/2026-10-04-etfe-trade-windows.md),
[machine receipt](docs/reviews/2026-10-04-etfe-trade-windows.json).

- All 225 missing pilot trade intervals captured for 68 contracts. Exact
  start/end batching produced 103 queries; all 105 GETs returned HTTP 200.
- Two invocations / 103.94 active seconds; first stopped after one request,
  resume preserved its three committed files and completed every page chain.
- Added 77,057 trade occurrences in 103 normalized partitions. Independent
  ordered raw-row, exact nanosecond, interval and logical-membership audits pass.
- Demanded-minute census: 4,626 rows; 2,200 have trades and bars, three trades
  only, 2,423 neither. Fifty-four whole intervals are empty; absence is unresolved.
- Seven observed trades lack corresponding bars in three SPY January 24-expiry
  contract-minutes. Exact keys and occurrences are in OBSERVATION_EXCEPTIONS.
- All 77,057 trades lack native IDs. 166 additional equal-time records occur
  in 130 minutes; preserve occurrence identity without inventing native order.
- Zero normalization quality flags; 116 focused tests pass. Raw 5.80 MB,
  normalized/audit 6.75 MB. No feature/execution/training admission claimed.
- Selected normalized total: 1,249 partitions / 1,955,680 rows, including
  152,856 option trades. Earlier stocks/options and causal pilot remain unchanged.

## Stopping point and next work

No ETFE job remains running. The pilot has zero remaining trade transport
intervals; full demand/history/admission and integrated ETFE-4.pilot stay open.

1. Implement the registered option trade/bar feature consumer from the selected
   fresh normalized data, preserving conditions, completed-window availability,
   missingness and ambiguous equal-time ordering. A captured empty response does
   not establish a valid zero-trade feature. Do not replace missing bars with fills.
2. Complete remaining option/context/TV components and full-window phase-B demand;
   holding/roll/physical-stock phase C remains. Resolve out-of-stock-RTH windows
   using dated option hours, not assumptions from stock-session labels.
3. Resolve historical listing/terms/actions, expiry close, trade-condition and
   publication provenance at admission. Usable history start remains null.
4. Complete the integrated capture/features/execution/dataset/training smoke and
   recovery/resource pilot before bulk work, freezes or model training.

## Pointers and constraints

Raw: `nn_meta/data_cache_etfe/alpaca-fresh-20261004-trade-windows-r0/`.
Normalized: `nn_meta/data_cache_etfe/normalized-20261004-trade-windows-r0/`.
Evidence: `nn_meta/validation/etfe-trade-windows-20261004-r0/`.
Raw plan SHA256: `e4eb9897d58af3ea9ea9596d0e7bf913b05b1fffc8e3cde26582b38d9ee40b4b`.
Normalized plan SHA256: `53ec002bc63e2a9ec291e98e859f23fe53a9272026705b593364fa8542012e47`.
Normalized root includes INDEPENDENT_AUDIT, DEMAND_AUDIT, TIMESTAMP_AUDIT,
DEMANDED_MINUTES.parquet and OBSERVATION_EXCEPTIONS. Raw root has RESUME_AUDIT.
The ZIP preserves metadata/sources and hashes for 209 local body/Parquet files.

Original `etfe-causal-20261004-r0/GLOBAL_DEMAND.json` stays immutable; the new
DEMAND_AUDIT records its captured successor status. Frozen sources require new
roots if changed. All market data is newly captured from Alpaca; no old inputs.
[Exact state](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#bounded-pilot-trade-capture),
[study](docs/specs/ETFE_TRADE_CAPTURE_20261004.md).
Preserve unrelated dirty work. No deployment, model training or economic verdict.
[Previous handoff](handoff-history/HANDOFF-2026-10-04-before-trade-windows.md).
