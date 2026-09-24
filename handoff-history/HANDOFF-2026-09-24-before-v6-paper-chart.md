# Handoff — 2026-09-24 — V7-2 resumed after full loader preflight

Read `TODO.md` first. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-loader-restart.md`. V7-1 is
complete under the agreed exclusion policy. V7-2 is actively building;
V7-3 has not started. Do not claim the 591-security/1,773-store gate is
complete until all stores are sealed and audited. Main is the operating
branch. The worktree has extensive unrelated pre-existing changes: stage
only exact owned files. Last V7 fixes are on origin/main at `83d3b6d`
and `c551654`.

## Independent active build

`healys-v7-catalog-build.service` started at 18:12:42 CDT on September 24,
main PID 3128252, `Restart=no`, four outer workers. Host-side systemd
showed it active at 18:21 CDT; the controller's 166/166 real-loader
preflight passed with zero failures at 18:18. The subsequent actual build
advanced to 426/591 complete securities, 1,281/1,773 proposal stores,
2,570 feature receipts and 1,281 sealed features at 18:21. The CLI reported
zero input-blocked securities and 348.4 GiB free. This is progress, not
completion evidence.

Monitor with `./venv/bin/python -m scripts.watch_v7_catalog --follow
--interval 5` in a fresh terminal. A sandboxed viewer can show service
`unknown`; use host-side `systemctl --user status
healys-v7-catalog-build.service --no-pager` for its real state. Its ETA
waits for a stable hour of completed-security samples. Do not start a
second V7 builder while the service is active.

## Repairs and evidence

The source-bound review is
`docs/reviews/2026-09-24-v7-last45-repair.md`. Final supplemental coverage is
`nn_meta/validation/v7-action-coverage-20260924-listed-span-restricted-v1`.
The original 45 deferred names gained bounded old-identity or fresh-raw
epochs, and nine other securities were restricted to one exact listed span
where admitted dates previously crossed an identity gap. These restrictions
explicitly exclude 2,246 formerly admitted sessions; a later gate audit
must review the exclusions. All 591 admitted-action checks passed (4,422
admitted events). The actual production loader passed all 166 remaining
securities; report:
`nn_meta/validation/v7-2-remaining-loader-preflight-20260924.json`.

The prior controller failed at 425/591 on a VMW eligible-source guard.
After it stopped, the builder guard was moved after admission filtering and
restricted to explicit nonadmitted mismatch dates. Its reuse contract now
permits two exact noncomputing review JSON additions and one earlier store
only when the old and current per-security coverage/policy panels are
identical. All 415 reuse-manifest stores and ten newly sealed stores passed
the receipt preflight. Two shortest-history five-minute stores were also
built as feature-path smoke tests. Full tests after fixes: 2,383 passed plus
18 subtests. The installed service unit points at the final supplemental
coverage and runs the loader preflight before scheduling workers.

## Next actions

1. Monitor the independent service's security/store counts and worker
   errors. If it stops, inspect the exact failed worker log and receipt
   before changing inputs or resuming. Preserve all valid sealed stores.
2. Keep `nn_meta/v7/`, shared `nn_meta` computational sources, and the two
   new `docs/specs/V7_LAST45_*_20260924.json` files byte-stable while the
   service runs; worker receipts bind their source hashes.
3. When 591/591 securities and 1,773/1,773 stores seal, perform the full
   V7-2 source, availability, variant, compact-size, receipt, and 100 GiB
   reserve audit. Only then consider checking 7-2 and starting 7-3.

Alias minute spans for ANTM, BYON, BBBY, NXH, MPT are preserved under
`nn_meta/data_v7/last45-alias-spans-20260924`; they were not spliced into
selected history. No second V7 builder was started during this repair.
