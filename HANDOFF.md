# New research version preparation; old short-DTE build paused

Updated September 14 Central / September 15 UTC, 2026.

## User's latest direction

Keep the existing training/evaluation dates. Build a separate research version
with all registered strategy/parameter variations across **1/5/15/30-minute
stock signals**, verified minute stock data for the full 449-symbol universe,
and **one-minute option execution using frozen MASSIVE bid/ask quotes**.
Complete that universe and validate the full pipeline before the long build.
Four worker processes remain the requested compute target. The user did not
ask to move the historical period or replace the deployed paper model.

Original training: **2024-08-26–2025-12-19**. Full model history:
**2024-08-26–2026-08-24**, with stock warmup from **2024-04-01**. Previously
inspected later periods remain revalidation, not untouched holdout.

Read [new-version scope](docs/specs/MULTITIMEFRAME_RESEARCH.md) and
[session review](docs/reviews/2026-09-14-v6-dashboard-and-multitimeframe-preparation.md).
TODO.md now leads with the new preparation checklist.

## Actual campaign state

`v6-short-dte-20260914-now` was resumed with four workers/two threads each,
24 GiB cap, CPU800%, 4 GiB memory reserve and the original nightly cutoff.
`scripts/resume_v6_short_dte.py` is an execution-only wrapper around the frozen
launcher. It verifies completed receipts and binds its resource plan/source.
Its copy and plan are in that campaign's `v6/execution/parallel-4/`.

Then the user changed scope. **Main service stopped; main timer disabled.**
21/449 completed symbols are preserved (20 original plus AMDL). Last status
is `paused`, reason `Service stopped`, at 2026-09-15T04:02:05Z. No short-DTE
model was trained. Do not restart this 15-minute campaign for the new version.
The read-only progress timer remains available. The session-chat update
state remains stopped from the user's earlier pause; do not rebind it.

Old scope SHA256:
`170b630e0d91ed0df705bdfbdcc3c26bc446ae2cf197b56bcb9ed37f7f60b59b`.
Scope/status: `nn_meta/campaigns/v6-short-dte-20260914-now/v6/short_dte_scope.json`
and `runs/status.json`. Frozen numerical code and existing artifacts preserved.

## Preparation completed and remaining

- Added `nn_meta/multitimeframe_catalog.py` and
  `scripts/prepare_multitimeframe_catalog.py`, with nine test cases. Stable
  IDs enumerate 2,817 parameter variants per timeframe, 11,268 per ticker,
  **5,059,332** combinations over 449 tickers before directions/DTEs/events.
  No winner selection or old signal cap. This is a planning inventory;
  full vectorization, per-timeframe support and execution are not implemented.
- Draft catalog and backup listing/report:
  `nn_meta/validation/multitimeframe-preparation-20260915/`. Original training
  dates are copied only after checking the baseline hash bound by the old scope.
- Stock backup inventory: 2,761 symbol/year files, 5.33 GiB, 2017–2026. Exact
  campaign matches: 220/221/221 for 2024/2025/2026. Files have not been restored
  or validated. Resolve aliases and listing dates before treating missing
  filenames as gaps. Local minute cache only has SPY; repaired full panel is 15m.
- Existing MASSIVE captures cover selected feature windows, not verified full
  entry/mark/exit/roll quote histories for the new universe. Do not claim data
  ready or treat option OHLCV aggregates as bid/ask quotes.
- Next: restore/repair minute coverage, implement bounded full-variant signal
  generation and timeframe-specific context/features, complete quote capture
  and execution, run full readiness/resource pilots, then freeze and launch.
  HTF auto-selection, opening-range and killzone rules need explicit timeframe
  handling; changing `INTERVAL` alone is insufficient. External Pine parity
  remains deferred/unverified. All thirteen indicator scopes stay included;
  eight source publications provide strategies, five provide features only.

Validation: **1,618 tests + 18 subtests passed**, 18 dependency warnings,
69.70 seconds (`/tmp/healys-multitimeframe-pytest.log`). No new-version
freeze/build/training has started. No credible duration estimate yet.

## Dashboard and execution/operating evidence (user's items 2–3)

Implemented and installed source changes in
`/home/healy/Coding/HealyLabsDashboard`: V6 Paper tab, filterable portfolio,
scoped export, closed legs/cycles, quote checks, relay versus server delivery,
and a read-only collector with a separate deduplicated evidence journal.
Main-repo source/patch copies: `integrations/dashboard/`; tests under `tests/`.

**Hosting not deployed; continuous evidence collection not activated.**
Home publisher still needs `V6_FORWARD_ROOT` and `V6_FORWARD_EVIDENCE`; exact
values and server deployment requirement are in the session review. Existing
privacy/auth rules are unchanged. Nine frontend tests, production build and
Chrome desktop/phone browser tests passed; screenshots were inspected.
Chrome executable: `/usr/bin/google-chrome-stable`. The user canceled a
bundled-browser download; do not install another browser unnecessarily.

Ledger last inspected: 4 open, 2 closed, 25 cycles, 0 rolls. Realized
contribution about -3.96% excludes unmarked open positions, so is not total
portfolio return. Collection does not invent marks or guarantee capturing
brief failed passes. Detailed implementation limits are in the review.

## Preserved V6 paper deployment

Home `/home/healy/Coding/HealysV6`; server `/home/mrhea/HealysV6`; runtime
`d6660af`. Broad-DTE 40-member release `v6-cash-repair-20260913`, 164 features,
449 symbols. Existing producer, refresh, relay and server delivery preserved.
No broker orders. Last inspected status was idle outside market hours; this
is an observation from this session, not a perpetual health claim.
Release/model activation details remain in the prior archived handoff and
`docs/reviews/2026-09-14-v6-forward-activation.md`.

## Workspace and continuity

Work is on `main`. The checkout and dashboard repo already had extensive
uncommitted work; preserve it and never stage `nn_meta/artifacts_v6/` wholesale.
Old handoff archived at
`handoff-history/HANDOFF-2026-09-14-before-multitimeframe-preparation.md`.
No background capture/test/browser processes from this preparation remain.
