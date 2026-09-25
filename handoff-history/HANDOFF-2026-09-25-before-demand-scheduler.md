# Handoff — 2026-09-25 — V7-2 complete; V7-3 started

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-25-before-v7-2-completion.md`.
Main is operational. Extensive unrelated dirty/untracked work predates this
session; preserve it and stage only owned changes.

## Current stage: V7-3

V7-1 and V7-2 are complete. Do not rebuild or modify the 591-security, 1,773-store
catalog at `nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`.
Its old-loader stores remain admitted by exact 415-security reuse plus ten
current-loader equivalence proofs. All numerical source hashes are preserved.

The new full daily context is `nn_meta/validation/v7-daily-context-20260925-full`:
591 × 1,129 = 667,239 rows, 564,453 admitted history sessions, all ten daily
features, SPY market context, reviewed actions, explicit gaps and dated sectors.
The saved-data audit passes 591 shards, input/source/receipt checks, arithmetic,
next-open clocks and 1,182 raw-input prefix replays. Summary missingness retains
short-history warmup and observed quote gaps. Completion evidence:
`nn_meta/validation/v7-2-completion-20260925` and
`nn_meta/validation/v7-2-full-daily-audit-20260925.json`.
Never overwrite the original `v7-2-final-deep-gate-20260925.json`: the daily
artifact binds its historical catalog-only checkpoint hash.

The actual first V7-3 entry-demand pilot completed for MTUM (`BBG004FPTZB8`):
29,843 proposals; 8,451 variants; 5,030 selected targets and 75 no-fresh-price
outcomes; 3,552 quote/trade requests across 76 contracts, one export batch.
Demand: `nn_meta/validation/v7-3-entry-demand-20260925/BBG004FPTZB8`.
Export: `nn_meta/validation/v7-3-entry-requests-20260925/BBG004FPTZB8`.
Launch evidence: `nn_meta/validation/v7-3-launch-20260925`.
Full scope is still 591 securities. No provider downloads occurred. This is
pre-decision feature demand only; V7-3 remains open for the full path scope.

## Next concrete work

Build the resumable all-security demand scheduler. Existing strict
`StoredProposals` and `entry_demand._parents` reject historical source hashes;
carry the exact existing equivalence proofs in a downstream adapter instead
of changing frozen stores or broadly disabling hash checks. The MTUM pilot
uses current-loader stores and passed the unmodified strict consumer.
Then union/measure requests, resolve dated option hours and standard references,
and capture entry, mark, exit, roll and applicable delivery paths. Preserve
missing/provider-failure outcomes; keep at most four workers, one inner thread,
100 GiB disk reserve and 250 GB acquisition ceiling. Do not infer a whole-build
ETA or download volume from the sparse pilot.

There is no running V7 build from this session: the catalog, daily build, audit
and first demand pilot all finished. The existing catalog progress meter stays
at 1,773/1,773 and does not monitor 7-3. Add stage-specific scheduler progress.
Review: `docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md`.
Builder/auditor/tests committed and pushed as `44fa6d5`.
Full suite: 2,401 tests, 18 subtests, 20 warnings. About 344.5 GB remains free.

## Other work carried forward

The V6 Alpaca bridge was implemented in the prior session (`75e2374`, `1b2da2f`,
both pushed). Fresh scanner and submission remain disabled; no broker orders
have been sent. The account-only monitor runs. Next V6 work is prospective
fresh scanner events, bridge preview and lifecycle handling before activation.
Never import the old simulator's four positions. Simulator and broker P/L
remain separate. See the archived handoff for bridge details.

V5/V6 after-close read-only incubator is enabled; its September 25 run still
needs checking. Massive decision is due October 2; V6 feed parity and older
historical option capture remain evidence requirements. No V6 or incubator
runtime was changed during this V7 transition.
