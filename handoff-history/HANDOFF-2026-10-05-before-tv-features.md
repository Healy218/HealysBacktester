# Handoff — October 5, 2026 — Option trade/bar components

## Focus and completed result

Continued fresh Alpaca-only ETFE with 0–5 DTE, including qualifying 0DTE.
Completed **ETFE-2.option-trade-bar-components** on the captured January pilot.
Measured runs completed October 4; their original study dates/IDs are retained.
[Review](docs/reviews/2026-10-04-etfe-option-features.md),
[machine receipt](docs/reviews/2026-10-04-etfe-option-features.json).

- Implemented all ten registered option trade/bar formulas, condition filtering,
  completed-window availability, field-level missingness and order handling.
- Preserved all 458,133 original logical events. 195,435 candidate links factor
  into 4,739 distinct windows; 262,698 still have no prior-date candidate.
- 1,803 windows have all ten diagnostic values, 192 partial, 2,744 all missing.
  Fully populated windows serve 68,862 links; none is model-feature admitted.
- Unknown equal-time ordering masks signed/classified features in 189 windows /
  8,065 links. Thirty windows / 3,387 links stay outside stock-session scope.
- Every real calculated window passed input reversal and extreme future-record
  injection. Independent recomputation matched every value, mask, reason and
  logical membership at unchanged rtol=atol=1e-12. 129 focused tests passed.
- Actual one-scope stop/resume preserved three files and computed eight remaining
  scopes. Successor compute 2.26 seconds, 0.67 GiB peak RSS, 4.38 MB root.
- No new downloads, simulation, labels, model fitting or deployment.

## Rejected first run and stopping point

Initial r0 independently failed a VWAP-minus-last rounding case: about -1.46e-12
bps versus zero, outside the declared tolerance. Replaced vector dot-product
accumulation with a stable weighted sum and added a constant-price regression.
Preserved r0 plan/source/output/AUDIT_REJECTION; selected new r1 passed the same
tolerance. Prior capture, normalization and causal milestones remain complete.

No ETFE job remains running. Full feature schema/admission and integrated pilot
remain open; a finite diagnostic value does not establish historical eligibility.

## Next work

1. Continue the registered feature map with remaining TV/context/other components
   on fresh inputs, retaining explicit source availability and missingness.
   The fifteen shared stock and ten option diagnostics are not the full schema.
2. Resolve dated selection/actions/option sessions/condition/publication evidence
   before admitting features; usable history remains null. Empty captures still
   do not establish valid no-trade minutes. Preserve the three missing-bar cases.
3. Complete full-window phase-B and holding/roll/physical-stock phase-C demand,
   and the integrated capture/features/execution/dataset/training smoke/resource
   and recovery pilot before bulk work, dataset freezes or model training.

## Artifacts and constraints

Selected: `nn_meta/validation/etfe-option-features-20261004-r1/`.
Plan SHA256: `808c721bf5bb6583e84e0b9b104f06961b6ed9ab03f161f72d05dcdb4f9c4183`.
PLAN/COMPLETE, per-scope window/link files, INDEPENDENT_AUDIT and RESUME_AUDIT
are local; evidence ZIP retains metadata/source and hashes for 36 Parquets
across r0/r1. Current code matches r1; r0 retains its original source snapshot.
Selected capture and normalization roots remain unchanged (1,249 partitions /
1,955,680 normalized rows). Diagnostic outputs are separate from this raw count.
[Exact state](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#option-tradebar-feature-component),
[study](docs/specs/ETFE_OPTION_FEATURE_PILOT_20261004.md).

Source-bound artifacts are immutable; changed consumers require successor roots.
Preserve unrelated dirty work, including pre-existing DECISIONS additions.
[Previous handoff](handoff-history/HANDOFF-2026-10-04-before-option-features.md).
