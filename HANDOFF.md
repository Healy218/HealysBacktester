# Handoff — 2026-09-27 — joined forecast and packed captures validated

Read TODO first. V7-3 remains current. Work on main; preserve all unrelated
working-tree edits. V7-1/V7-2 remain complete. No bulk acquisition or training
has launched. All preexisting freezes, including demand and cleanup receipts,
remain intact. Prior handoff: handoff-history/HANDOFF-2026-09-26-before-joined-packed-capture.md.

## Completed in this session

- Exact joined sampling census over 591 demand databases: 10,941,828 ranges,
  no added seconds. 60 strata × 12 paired samples = 1,440 captures over 376
  securities; all passed, 1,168,551 records, 86.21 seconds for network capture.
- New immutable indexed packed archives with bounded reads, raw hash checks,
  original manifests, exact request coverage, interrupted-write/failure handling,
  quota reservation and reserve guards. V1 and V2 sources/artifacts are both
  bound and retained; do not edit them in place without version treatment.
- V2 integer deltas and byte-shuffled IEEE doubles preserve canonical bytes,
  types/null/missingness, nanoseconds, order and duplicate prints. Estimated
  entry packs: 139.17 GB mean / 170.74 GB mean + 3 SE. Including measured
  routing: 142.39 / 173.95 GB. Three SE is not a hard bound.
- 126 prior quality requests and 12,760 sampled original frozen requests pass
  raw/causal archive parity. Five additional source-bound purchase windows
  passed direct-to-v2 capture and real midpoint fill/mark consumers, one/year.
  This is not full trade-path, portfolio or return evidence.
- Exact pre-entry dated demand: 2,223,844 contract/date references, 301,213
  root/date hours references, all 591 securities. Per-security SQLite lists
  are sealed under v7-dated-reference-demand-20260927.checkpoints.
- 720 sampled references captured: 715 verified standard, five HTTP 404s.
  Exact-date alternate list probes (active and expired) found no exact matches:
  CMA230630C00041000 / 2023-06-22; FANG220520P00130000 / 2022-05-18;
  MSTR230630P00320000 / 2023-06-27; RH230630P00290000 / 2023-06-22;
  VFC230630C00019000 / 2023-06-28. No substitutes or assumed terms admitted.
- Thirteen named Nasdaq hours pages captured. Historical changes are real;
  do not use today's ETF hours across history. IVV notice 2026-17 conflicts
  internally (2026 publication, 2025 body effective year); unresolved.

## Capacity and pending decisions

Capacity receipt: nn_meta/validation/v7-joined-capacity-review-20260927.
Local apparent project: 437.831 GB; MRHA historical archive: 35.107 GB.
Internal free: 286.242 GB at snapshot, with 20 GiB reserve unchanged.
Acquisition final ledger: 69,017,114,207 / 250,000,000,000 bytes, no reservations.
Recheck before launch. Reflink physical savings must not be credited logically.

Entry plus routing and conservative sampled-reference allowance: 175.693 GB
at mean+3SE, leaving only ~5.29 GB for additional execution paths/recovery.
Project stress: 613.524 GB locally / 648.631 GB including MRHA. Both exclude
held-path additions, assembly/training outputs and in-flight/recovery allowances.
The existing 250 GB acquisition / 640 GB project caps have not changed.

Two async questions were sent; no answer was present at this handoff:
1. Does the 640 GB project cap include MRHA's historical archive?
2. Keep the five missing references unresolved, or prepare an explicit
   affected-path exclusion policy for review? Preparing is not admission.
Do not infer either answer or change policy silently.

## Next work, still V7-3

Resolve source-backed dated hours and missing references; derive/forecast actual
purchase/mark/exit/roll/physical-delivery demand. A complete full-path budget
is required before bulk launch. Then implement/run resumable full-scope packed
scheduling with the reviewed limits. The new direct packed CLI is bounded
validation, not the full scheduler. The indexed reader is tested but the
production assembly adapter still needs explicit integration/binding in 7-5.

Legacy scripts/v7_readiness.py remains false and needs a later explicit
migration to the completed 7-1/7-2 proof model and current amendments. Its
active amendment check and generic missing evidence (including old 222-column
terminology) are not a reason to rewrite freezes or revoke completed milestones.
Full execution, assembly/folds, resource/recovery and final readiness remain.

## Evidence and validation

Review: docs/reviews/2026-09-27-v7-joined-packed-capture.md.
Evidence roots under nn_meta/validation:
- v7-joined-volume-sample-20260926
- v7-joined-packed-forecast-20260926, v7-joined-packed-v2-forecast-20260926
- v7-packed-quality-20260926, v7-packed-index-proof-20260926
- v7-direct-packed-fills-20260927, v7-direct-packed-fill-consumer-20260927
- v7-dated-reference-demand-20260927, v7-joined-capacity-review-20260927
Raw packs/references/pages remain under nn_meta/data_v7 in matching named roots.
All nine sealed roots and declared direct parent/source hashes verified.

Final full suite: 2,441 passed + 18 subtests, one skipped, 20 warnings, 123.97s.
Earlier run caught source drift while new files were being authored; the final
run was performed with stable sources and passed. Ten focused pack/encoding/
routing/split tests pass. No source-bound numerical producer was edited.
October 2 subscription, Alpaca bridge and incubator remain separate tasks.

Implementation committed as `772cc0d`; evidence/docs are the following scoped commit.
