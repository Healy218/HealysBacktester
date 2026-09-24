# Handoff — 2026-09-24 — V7-2 last-45 source repair

Read `TODO.md` first. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-last45-repair.md`. V7-1 remains
complete under its agreed exclusion policy. V7-2 is running; V7-3 has not
started. Do not claim the 591-security/1,773-store gate is complete until
every store is sealed and audited. Main is the operating branch. There is a
large pre-existing unrelated dirty worktree; stage only exact owned files.

## Independent active build

`healys-v7-catalog-build.service` remains active under PID 3093731, zero
restarts at the latest host-side check. It uses four outer workers and
`Restart=no`. The current controller still uses the September 21 base
coverage plus September 24 reviewed-v2 supplemental coverage and explicitly
defers the original 45. At the last read-only snapshot it had 425/591
complete securities, 1,275/1,773 proposal stores and 348.6 GiB free.
Run `./venv/bin/python -m scripts.watch_v7_catalog --follow --interval 5`
in a fresh terminal to monitor the same output. Its revised display separates
45 input-blocked names and estimates only runnable progress after a full hour
of data. A sandboxed one-shot viewer may show service `unknown`; host-side
`systemctl --user show` showed active. Do not start a second worker process
while this service is active.

## Last 45 repair completed on separate frozen inputs

The exact source-backed review is
`docs/reviews/2026-09-24-v7-last45-repair.md`. Final coverage is
`nn_meta/validation/v7-action-coverage-20260924-last45-single-epoch-v1`.
It admits a bounded old-identity or fresh raw interval for exactly the 45
original zero-admission securities: 28,460 added sessions, zero action-event
or identity-event changes, no inferred factor/successor/deliverable, and no
held path crossing a boundary. `check_admitted_actions` passes all 591 IDs
and 4,453 admitted events. The real active loader passes 41/45, recorded in
`nn_meta/validation/v7-last45-full-loader-preflight-20260924.json`.

Four failures are loader guard placement, not absent data. CCL old ID
`BBG000BF6LY3`, XOM old ID `BBG000GZQ728`, and RKLB old ID
`BBG00Y61SZL5` have 16/22/4 unmatched eligible dates respectively after
their old selected history ended. All those dates have nonadmitted coverage.
LAZR `BBG00MS90LK2` has two selected identity spans split at a noncash
boundary, but its admitted interval is one span. A temporary exact copy
`scripts/build_v7_proposals_probe.py` moves continuity checking after
coverage filtering and checks mismatched eligible dates against explicit
nonadmission. All four pass this probe with bound raw minutes and the final
coverage receipt. The original `scripts/build_v7_proposals.py` has **not**
been changed because active workers bind its hash. All 415 reuse-manifest
securities pass the old continuity and eligible-source guards, so the two
new guard conditions are a no-op for their selected inputs.

Five named alias spans (ANTM, BYON, BBBY, NXH, MPT) were captured 16/16
raw/all tasks under the shared quota at
`nn_meta/data_v7/last45-alias-spans-20260924`; eight daily shards are at
`nn_meta/validation/v7-last45-alias-daily-20260924`. These have not been
spliced into selected history. The 45's admitted epochs use existing bound
raw stock data. Preserve the alias captures for any later full-history review.

## Source fingerprint issue to resolve on resume

The two new `docs/specs/V7_LAST45_*_20260924.json` review files enter the
broad feature source map. They were briefly moved while two in-flight
feature declarations already bound them, then immediately restored. Keep
them byte-identical until the active service stops. The 415 reused stores
have no changed or removed source hashes; compared with the current source
map, 276 only lack those two JSONs plus already permitted catalog audit/reuse
modules, and 139 lack those two JSONs plus the reuse module. Newly sealed
stores may or may not bind the JSONs depending on their start time. Before
resuming, explicitly permit just those two noncomputing review additions in
the reuse compatibility proof and the audit helper's own code hash change;
verify every sealed store rather than relabeling any receipt.

## Next exact sequence

1. Let the existing service finish its scheduled stores. Check its exit,
   sealed count, source hashes, disk reserve and any worker errors. It should
   exit nonzero with the 45 explicitly deferred; that is expected until the
   repaired coverage is consumed.
2. With no active workers, apply the two tested guard changes from
   `scripts/build_v7_proposals_probe.py` to the original builder. Keep the
   original builder's other logic intact. Audit the 415 reused stores for
   equivalence under the new guard order.
3. Add the narrow review-file/audit-helper exception to the catalog reuse
   checker, run full tests and exact controller preflight, then point the
   service's supplemental coverage at the final last-45 artifact. Resume
   only incomplete stores with the same four-worker limit. Audit all 1,773
   stores and the 100 GiB reserve before closing 7-2 or starting 7-3.

Current verification: full suite 2,382 passed plus 18 subtests (112 seconds);
all new scripts compile; action-event parity and 415 old-guard equivalence
audits pass. No second V7 builder was started in this repair session.
