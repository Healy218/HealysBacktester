# Handoff — 2026-09-26 — duplicate cleanup and MRHA V6 archive complete

Read TODO first. V7-3 remains current. Work on main; preserve unrelated dirty
files. Prior handoff: handoff-history/HANDOFF-2026-09-26-before-authorized-storage-move.md.

## User authorization and completed storage work

The user explicitly requested removal of the byte-identical extra copies and
moving the 9.54 million-file historical V6 tree into an archive folder on MRHA.
Both are complete. No current V7 freeze/demand/raw lineage or live V6 data moved.

- 4,690 redundant allocations / 53.88 GB logical duplicates replaced with
  verified independent Btrfs reflinks. Every historical path/hash remains;
  writes remain independent. Measured free-space gain: 31.67 GB.
  Evidence: nn_meta/validation/storage-duplicate-reclamation-20260926.
- All 9,541,723 files and 2,066,117 directories in the old V6 expanded-input
  tree were preserved in 454 tar.zst archives totaling 35,106,688,686 bytes.
  MRHA: /run/media/healy/MRHA/HealysBacktester/v6-archive-20260926,
  UUID 62C9-C390. Existing drive backups were untouched; drive remains mounted.
- External SHA256, complete GNU tar source comparisons, actual archive-member
  census and real quote/trade/manifest restoration all pass. Restored payloads
  decode 309 quotes and one trade. A final external rehash preceded retirement.
- The entire loose nn_meta/expanded_inputs/v6-local-20260906 tree and all local
  staging tar.zst copies are removed. The adjacent .ARCHIVED.json locator,
  local receipts and external RESTORE.md explain restoration. Do not recapture
  merely because the archived tree is now absent.
- Evidence: nn_meta/validation/v6-archive-migration-20260926, including
  VERIFIED, MEMBERS-VERIFIED, RETIRED, retirement journal, staging cleanup,
  restore proof and final-capacity snapshots. Scripts: archive_v6_inputs.py
  and reclaim_verified_duplicates.py. Tools/initial duplicate proof pushed
  as 9b1b826; final receipts/docs are the current session's follow-up commit.

## Capacity and next V7 work

Internal free space measured 303,613,919,232 bytes (~303.61 GB), ~72.07 GB
above the pre-cleanup value. ~282.14 GB remains above the 20 GiB reserve.
MRHA has ~743.73 GB free. Recheck before launching: these are snapshots.
Reflinks save physical storage, but existing names/inodes still count in
logical-byte budgets; do not subtract their saving twice.

No bulk option acquisition or training launched. Current capture planning keeps
20 GiB headroom; 250 GB acquisition and 640 GB project caps remain unchanged.
Original bound writers retain historical guards. Next: representative joined-
range volume forecast and packed/indexed capture storage, then remaining V7-3
references/hours and full execution-path coverage. The exact adjacent-window
proof still passes 126 original request reads in six real cases (62 captures
versus 12 joined). Dated references, fills/marks/exits/rolls/delivery, assembly
and readiness remain before training. Current V7-1/7-2 are complete.

Review: docs/reviews/2026-09-26-authorized-storage-reclamation.md.
Post-move full suite passed: **2,432 tests + 18 subtests**, 20 warnings,
136.58 seconds. The real archived source tree was absent during this run.
All five focused storage tests passed, including fail-closed deletion guards.
Test temporary directories were then removed. Post-tests free space changed to
297,025,257,472 bytes (~297.03 GB), ~275.55 GB above reserve; use this newer
snapshot instead of the immediate post-cleanup 303.61 GB figure above.
Other filesystem activity is not attributed to this cleanup. Final binding and
post-move-tests.json are saved beside the archive receipts.
Hourly completion timers remain disabled. October 2 subscription, Alpaca bridge
and incubator work remain separate carried-forward tasks.
