# V7-2 catalog recovery — 2026-09-24

The September 18 action and coverage artifacts passed the full admitted-event
comparison (4,305 events). The September 21 repaired coverage changed the
admitted event set, but the installed catalog service retained the September 18
ordinary-action path. That installed pair disagreed on 96 securities. The
controller continued past failed securities and systemd retried it nine times,
while its progress counter counted sealed stores without representing failures.
This was a configuration regression after the earlier matching checks.

The corrected `v7-dividends-complete-20260918` action artifact matches the
repaired coverage for all 591 securities and all 4,314 admitted events. The
existing catalog held 423 fully completed securities. Comparing each completed
feature declaration's typed actions with the corrected artifact found 415
equivalent securities and eight with changed actions. The 415 also bind the
current repaired coverage receipt. Every source file recorded by their build
declarations still hashes identically; only the later read-only audit modules
`catalog_audit.py` and `catalog_reuse.py` were added to the producer's broad
source inventory. The reuse verifier permits only those two additions. Their
sealed stores and original receipts remain unchanged. A separate
`v7-2-catalog-reuse-20260924.json` manifest records all three feature/proposal
summary receipt hashes for each security and is reverified before the runner
starts. It is an explicit computation-equivalence proof, not a relabeling of
the original action-file lineage.

The eight changed completed securities and four partial checkpoint directories
were moved, without deletion, to the sibling
`v7-2-full-catalog-20260922-rebuild-5-15-30-superseded-20260924` directory.
The active catalog retains 415 complete securities; 176 securities remain to
build. Before workers launch, the runner compares the configured action events
against all admitted coverage and verifies the reuse manifest. It stops
scheduling new securities at the first worker failure. The service no longer
restarts on failure. Full post-seal validation of all 1,773 stores, source
bindings, disk reserve and recovery remains required before item 7-2 closes.

The full suite passed 2,378 tests and 18 subtests before service installation.
The existing V7 service was stopped before checkpoint archiving; no second
controller was started. This note records preparation and does not claim the
remaining build or V7-2 gate is complete.
