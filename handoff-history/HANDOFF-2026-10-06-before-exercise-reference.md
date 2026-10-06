# Handoff — October 6, 2026 — ETFE exact capture and dated-input policy v1

## Focus and result

1. **Exact-option capture completed** (`alpaca-fresh-exact-options-20261006-r0`):
   3,036/3,036 jobs, 2,275,130 normalized occurrences; full independent audit
   (`FULL_CAPTURE_INDEPENDENT_AUDIT.json`) reconciles raw-to-Parquet and
   capture-to-union. 194 bar / 112 trade windows returned no rows.
2. **ETFE-0 dated-input policy v1.** Alpaca has no point-in-time contract terms,
   so the user selected declared rules
   ([spec](docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md)):
   - Economics from the deliverable. All 43,720 `multiplier=0` records are
     standard 100-share contracts expiring Jan–Apr 2024. Five adjusted `1SPY`
     contracts are excluded. 452,342 of 452,347 are admitted.
   - Availability = first fresh observation (bar end or trade) at or before the
     decision. All 227,529 exact-window candidate rows pass by entry start.
   - Settlement from the provider calendar, cross-checked with the SEC trade-date
     rule (T+2 before 2024-05-28, T+1 after, bank holidays skipped): 689/690
     match. Declared exception: 2025-01-08 (Carter mourning day).
   - Actions known from the session after declaration (33/33 before ex-date).
     QQQ's 2024-03-18 payable date comes from Invesco (April 30).
   - Research start 2024-01-18 09:30 ET. VOO recursive indicators re-warm after
     each of the 12 missing minutes (`rewarm_mask`), with no filling.
   - Independent audit recomputes every output by a different route; all match.
     7 new tests; 335 ETFE tests pass.

Both auditor failures during development were auditor bugs (symbol length,
float64 nanosecond loss), not resolver defects. Exit code 2 from
`acquire_etfe_alpaca.py run` and `normalize_etfe.py run` means "work remains".

## Next actions

1. **Remaining ETFE-0 decisions** (user's call): official exercise/expiry
   reference price (candidate: underlying's final regular-session SIP minute
   close) and SIP quote size representation. P1, R1/R2 and action revisions stay
   documented as unmodeled unless the user wants them pursued.
2. **ETFE-1.path-demand:** with v1, the `dated_selection_unresolved` candidate
   rows can become policy-eligible selections. Next, run the existing synthetic
   execution/expiry/integration ledgers on real selections to produce execution
   receipts and holding/roll/exercise windows, then size the path capture.
3. Apply `rewarm_mask` with each variant's declared warmup in the ETFE-2 feature
   build. ETFE-4.pilot, freeze, build, training and evaluation remain later.

## Selected artifacts

Policy: `nn_meta/validation/etfe-dated-policy-20261006-r0/` (RESOLUTION,
CONTRACTS.parquet, ACTIONS, VOO_GAPS, INDEPENDENT_AUDIT).
Capture: `nn_meta/data_cache_etfe/alpaca-fresh-exact-options-20261006-r0/`;
typed `normalized-20261006-exact-options-r0/`.
Window demand: `nn_meta/validation/etfe-exact-windows-20261006-r0/`.

No ETFE-0 closure, feature/execution admission, build or training is implied.
Preserve unrelated dirty V6/V7 work, including uncommitted DECISIONS hunks.

[Previous handoff](handoff-history/HANDOFF-2026-10-06-before-dated-policy.md).
