# Handoff — October 4, 2026 — 0DTE, normalization and expanded acquisition

## User direction and completed result

User permits same-day options when signals qualify and requests normalization
and expanded acquisition. Current v4 scope: **0–5 calendar DTE** at entry/roll;
default targets 0/1/5, conditional weekly 2/4, no target 7. Signal, dated expiry
clock and strict close-minus-15-minute cutoff remain. Missing expiry clock blocks
entry; same-day IV time uses positive remaining seconds, not an invented day.
[Current scope](docs/specs/ETFE_SCOPE_0DTE_20261004.json),
[successor contract](docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md).

## Completed work and evidence

- 254 new live GETs, all HTTP 200: calendar 1, stock 192, discovery 48, options 13.
  The stock download resumed after its 128-request limit; all planned work finished.
- Added 96 stock-month and 60 option discovery/bar/trade partitions. Combined
  fresh stock requests span January 1, 2024–October 2, 2026 for all three ETFs.
- Typed Parquet normalization complete for 186 partitions / 1,677,986 rows:
  1,589,090 stock bars, 5,399 option bars, 75,799 trades, 7,698 discovery records.
- Options are four-date transport samples; new early-close/busy strata cover
  November 29, 2024 and April 4, 2025, with actual sampled DTE 0/5. Not full demand.
- SPY/QQQ cover all 268,410 expected regular minutes. VOO is missing twelve across
  ten dates; exact intervals retained as unresolved gaps, with no synthetic bars.
- Every raw row occurrence matches normalized raw JSON in order, with source
  hashes and counts verified. No implemented row quality flags fired. Stock
  session labels do not certify option-session hours or economic terms.
- Real normalization stop/resume preserved two committed files. Normalized roots
  total about 164.4 MiB; peak normalization RSS 208.2 MiB. 87 focused tests pass.
[Review](docs/reviews/2026-10-04-etfe-normalization-expansion.md),
[machine receipt](docs/reviews/2026-10-04-etfe-normalization-expansion.json).

## Stopping point and next actions

1. Build the full option/context demand census from registered signals and
   current 0–5 DTE policy; expand beyond the four option transport dates under
   measured budgets. The stock-month expansion is already complete.
2. Consume normalized inputs in causal 1/5/15-minute feature/strategy components;
   keep VOO gaps, warmup and unavailable features explicit. Resolve historical
   eligibility and dated option expiry/session clocks at their consumer boundary.
3. Establish earliest scoped options coverage and full required-input inventory;
   January stock padding is not a verified options floor or model warmup grant.
4. Complete integrated ETFE-4.pilot feature/ledger/dataset/training-smoke resource
   and recovery proof, then full coverage/build/freezes in ROADMAP order.

No running ETFE download job remains. No live service, model training, dataset
freeze or performance verdict. Fresh Alpaca only; no old project data/metadata.

## Exact pointers and constraints

Current setup: `nn_meta/validation/etfe-setup-20261004-0dte-r0/`; SHA256
`39d2d8cf8129e26ec3be4299ff12e94a9d71f38796e3272f7d5681006694ad23`.
Verify with `scripts/prepare_etfe_0dte.py verify --root` that path, using venv Python.
Normalized: `nn_meta/data_cache_etfe/normalized-20261004-main-r0/` and
`normalized-20261004-strata-r0/`; each has PLAN/NORMALIZED/INDEPENDENT_AUDIT receipts.
Raw roots, calendar and CLIs: [CURRENT_STATE](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[operating reference](docs/reference/ETFE_SETUP.md). Evidence ZIP indexes payload
hashes/reports; large raw/Parquet payloads stay local. Preserve old setup/source
snapshots and unrelated dirty work. V7 archive complete; other campaigns paused.
[Previous handoff](handoff-history/HANDOFF-2026-10-04-before-0dte-normalization.md).
