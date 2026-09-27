# Handoff — 2026-09-27 — five dated-reference blackouts implemented

Read TODO first. V7-3 remains current; V7-1/V7-2 remain complete. Work on main
and preserve unrelated dirty/untracked work. No bulk acquisition or training
launched. Original proposal, demand, packed and cleanup freezes remain intact.
Previous state is archived in
`handoff-history/HANDOFF-2026-09-27-before-contract-blackouts.md`.

## User decisions and completed implementation

The user permits MRHA disk if necessary. They also asked to treat the five
missing-reference instances as a weekend. Implemented as finite exact
contract/date research-path blackouts, without modifying exchange calendars:

- CMA230630C00041000 / 2023-06-22: 122 entry proposal/target outcomes.
- FANG220520P00130000 / 2022-05-18: 8,520.
- MSTR230630P00320000 / 2023-06-27: 310.
- RH230630P00290000 / 2023-06-22: 246.
- VFC230630C00019000 / 2023-06-28: 3,772.

Total frozen entry impact: 12,970 proposal/target outcomes, 294 selected
clock/target outcomes, 192 original requests. Full held-path impact is not yet
counted. All 720 sampled references have explicit treatment: 715 verified
standard and five blackouts. Exact 404 and both same-date alternate-list probes
are bound. No downloads or mutation of original demand were needed.

`nn_meta/v7/contract_blackouts.py` wraps the real feature/replay consumers;
`scripts/build_v7_blackout_dataset.py` requires the sealed `--blackouts` root.
Affected outcomes retain their census, source hashes and legitimate partial
ledger, but produce no numerical feature row or label. A held position reaching
a blackout is never presumed closed/settled. Earlier closed paths are unchanged.
No alternative contract is selected. New missing references do not silently
join the policy. These are retrospective research exclusions, not historical
eligibility or permission to rerank shared-capital portfolios.

Review: `docs/reviews/2026-09-27-v7-contract-reference-blackouts.md`.
Declaration: `docs/specs/V7_CONTRACT_REFERENCE_BLACKOUTS_20260927.json`.
Sealed evidence under `nn_meta/validation`:
- `v7-contract-blackouts-20260927`
- `v7-contract-blackout-impact-20260927`
Producer: `scripts/compile_v7_contract_blackouts.py` (defaults name all parents).
Sources are now bound; do not edit them in place without version treatment.

## Storage and earlier completed work

The joined forecast and lossless packed implementation are complete; see
`docs/reviews/2026-09-27-v7-joined-packed-capture.md` and previous handoff.
591 demand stores, 10,941,828 joined ranges, 2,223,844 contract/date references,
301,213 root/date hours references. 1,440 representative captures, 376 securities,
1,168,551 records. V2 entry+routing: 142.39 GB mean / 173.95 GB mean+3SE;
with sampled reference allowance: 175.693 GB. Three SE is not a hard bound.
12,760 original requests passed indexed-read parity; five additional source-bound
purchase windows passed real fill/mark consumers. Full trade paths remain open.

Latest capacity receipt: `v7-joined-capacity-review-20260927`.
Local apparent project 437.831 GB; MRHA historical archive 35.107 GB; internal
free 286.242 GB at snapshot. Acquisition ledger 69,017,114,207 / 250,000,000,000
bytes, no reservations at prior session end. Recheck before launch.
Project stress 613.524 GB local / 648.631 GB including MRHA, before held-path,
assembly/training and recovery allowances. Location permission does not raise
the numerical 250 GB acquisition / 640 GB project caps or 20 GiB free reserve.

## Next work — still V7-3

Resolve source-backed historical hours (13 Nasdaq pages retained; IVV notice
2026-17 has a contradictory effective year). Resolve remaining full-scope dated
references subject to the finite blackout policy. Derive actual purchase, held
mark, exit, roll and physical-delivery demand and count blackout crossings.
Forecast the complete acquisition/assembly/training/recovery budget before bulk
launch. Then finish/run resumable full-scope packed scheduling with reviewed
limits. The direct packed CLI is bounded validation, not the full scheduler.

The indexed reader is tested; full production assembly/packed integration,
physical/shared-capital execution, folds and final readiness remain open. The
new blackout launcher wraps the existing local loader; it does not certify those
remaining integrations. Existing assembly.py/dataset_inputs.py and their tests
are preexisting untracked work, deliberately not included wholesale in this
scoped commit. Preserve them.

Legacy scripts/v7_readiness.py still needs an explicit migration to the completed
7-1/7-2 proof model/current amendments. Its stale checks/222-column terminology
are not reasons to rewrite freezes or revoke completed milestones. Training
readiness remains false. October 2 subscription, Alpaca bridge and incubator
remain separate tasks.

## Validation

Seven focused blackout tests pass (actual assembly/replay, exact scope, retained
held/roll ledgers, unchanged earlier close, source/declaration evidence guards).
New launcher argument/help path passes. Full-suite result follows below.

Full suite: 2,448 passed, 18 subtests passed, one skipped, 20 warnings, 115.95s.
