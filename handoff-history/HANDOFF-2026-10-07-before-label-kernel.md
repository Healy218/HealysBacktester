# Handoff — October 6, 2026 — ETFE dated-input policy complete (exercise reference, quote size)

## Focus and result

Earlier today: exact-option capture completed (3,036 jobs, 2,275,130 rows) and
dated-input policy v1 applied (economics, first-seen availability, settlement,
actions, history start, VOO re-warm). This session then settled the last two
ETFE-0 input decisions with the user
([policy](docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md)):

- **Exercise reference = listing venue's closing-auction print** from fresh SIP
  trades. Probe, then three yearly roots (1,487 expiry-session windows, about
  3.0M trades, 322 MB total). Extraction v2 (`nn_meta/etfe/exercise_reference.py`):
  listing-venue `M`, else its `6` closing cross; Nasdaq `Q`/`T` for QQQ.
  1,486/1,487 resolved; **QQQ 2026-08-20 unresolved** (no auction print captured).
  Median 0.007% from the 15:59 bar close; max 0.96% on 2025-04-09.
  Independent recomputation matches.
- **Strict OCC $0.01 rule** in decimal cents; 330 pins within $0.05 reported.
- **Quote size:** ×100 before 2025-11-03, shares after. Pilot medians step from
  2–6 to 80–360 exactly at that date in all three ETFs.
- 341 ETFE tests pass. Each capture used one process (about 135 MiB,
  network-bound at 1 request/s); no worker pool was needed.

**Trap hit and fixed:** capture roots pin their listed source files, including
their spec (`ETFE_CLOSING_AUCTION_20261006.md`, `closing_reference.py`). I edited
the spec after the capture and restored it from the root's `source/` copy.
Record results in unpinned docs. Extraction changes go in a new module.

## Next actions

1. **ETFE-1.path-demand:** select policy-eligible entries from the 227,529
   candidate rows; run the execution/expiry/integration ledgers on real
   selections using these references and settlement dates; derive holding, roll
   and exercise windows; size their capture.
2. Decide whether to chase QQQ 2026-08-20 (a one-request wider-window successor)
   or leave it unresolved.
3. ETFE-2 feature build applies `rewarm_mask`; size it with
   `scripts/lib/autosize.sh`. Later gates are unchanged.

## Selected artifacts

`nn_meta/validation/etfe-dated-policy-20261006-r0/`,
`nn_meta/validation/etfe-exercise-references-20261006-r0/`,
`nn_meta/data_cache_etfe/alpaca-fresh-closing-auction-*-20261006-r0/`,
`nn_meta/data_cache_etfe/alpaca-fresh-exact-options-20261006-r0/` +
`normalized-20261006-exact-options-r0/`.

P1, R1/R2 and action revisions remain documented as unmodeled. No ETFE-0
closure, build or training is implied. Preserve unrelated dirty V6/V7 work,
including uncommitted DECISIONS hunks.

[Previous handoff](handoff-history/HANDOFF-2026-10-06-before-exercise-reference.md).
