# Handoff — October 5, 2026 — Thirteen-source TV features

## Focus and completed result

Continued fresh Alpaca-only ETFE, actual 0–5 DTE including qualifying 0DTE.
Completed **ETFE-2.tv-components**: all 96 registered projections across thirteen
numerical sources, on SPY/QQQ/VOO at 1/5/15 minutes.
[Review](docs/reviews/2026-10-05-etfe-tv-features.md),
[machine receipt](docs/reviews/2026-10-05-etfe-tv-features.json).

- Rebuilt January 2–19 stock prefixes from fresh normalized minutes; observed
  every January 18–19 closed bar: 2,964 observations, all 458,133 event links.
- 256,822 finite value cells / 27,722 explicit missing cells; field-specific
  readiness, float64 diagnostics, uint8 masks and reasons. Admission is false.
- Calendar-anchored HTF groups, causal minute ORB/HLC3 VWAP, gap taint and no
  initialized-state zeros before prerequisites. No old data/metadata inputs.
- Independent scalar projection/ATR/mask/reason/membership reconciliation passed.
  This does not independently reimplement kernels or establish Pine parity.
- Eighteen real prefix boundaries and future perturbations passed at unchanged
  rtol=atol=1e-12. All 143 focused ETFE tests passed, including fourteen new tests.
- Actual one-scope stop/resume preserved four receipt/payload files; eight more
  scopes completed. Compute 76.14 seconds, peak RSS 0.94 GiB, root 11.19 MB.
- No downloads, simulated execution, labels, training or deployment this session.

## Option-window clarification and stopping point

The earlier ten option diagnostics remain complete and unchanged: 1,803 of
4,739 windows have all ten. The 2,936 incomplete windows comprise 2,714 with
unresolved observations, 30 outside stock-session scope, 189 with ambiguous
trade ordering, and three with trades but missing bars. The last two groups
retain partial features; missing observations are not confirmed zero activity.

No ETFE process remains running. Full feature schema/admission and integrated
ETFE-4.pilot remain open. Finite diagnostics do not establish eligible entries.

## Next work

1. **ETFE-2.remaining-components:** daily stock/option context, event/contract/
   sector/parameter fields and variant projections from the frozen feature map.
   Check formulas against the 0–5 DTE successor; do not reuse stale /9 scaling.
2. Resolve dated actions/selection/option sessions/terms/publication evidence
   before admission. Usable history remains null; preserve all absence cases.
3. Complete full phase-B and holding/roll/physical-stock phase-C demand, then
   integrated capture/features/execution/dataset/training smoke and resource/
   recovery checks before bulk build, final freezes or training.

## Artifacts and constraints

Selected root: `nn_meta/validation/etfe-tv-features-20261005-r0/`.
Plan SHA256: `796a24e7a3a659513f8317fbdd89f65d6c9f28afbf5e40f527cd6f369c438bab`.
PLAN/COMPLETE, nine receipts, INDEPENDENT_AUDIT/RESUME_AUDIT and 27 Parquets
are local. Evidence ZIP contains 58 metadata/source members and payload hashes.
Selected normalized inputs remain 1,249 partitions / 1,955,680 market rows.
[Exact state](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#thirteen-source-tv-feature-component),
[study](docs/specs/ETFE_TV_FEATURE_PILOT_20261005.md).

Source-bound consumers/artifacts are immutable; use successor roots for changes.
Preserve unrelated dirty work, including pre-existing DECISIONS/EXPERIMENTS edits.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-tv-features.md).
