# V7 7-3 — full execution queue and reference adjudication

September 28, 2026. Gate 7-3 remains open. Entry capture and original dated-reference
capture stay complete; this work advances actual path discovery and resolves the
known finite reference exceptions without changing the frozen catalog.

## Reference evidence and approved scope

All 10,817 original 404 pairs were queried against both exact dated contract-list
variants (expired false/true). Independent reconciliation verified 21,634 retained
responses across 339 packs, with zero exact matches. Raw recovery evidence is
21,069,455 bytes. Nine remaining nonstandard rows contain actual USD deliverable
legs; those terms are not synthesized into standard 100-share options.

- Recovery: `nn_meta/data_v7/reference-list-recovery-20260928/`.
- Full audit/proposed list: `nn_meta/validation/v7-reference-recovery-audit-20260928/`.
- Entry-impact census: `nn_meta/validation/v7-reference-entry-impact-20260928/`.
- [Explicit user approval](2026-09-28-v7-reference-exclusion-approval.json).
- Compiled policy: `nn_meta/validation/v7-contract-blackouts-20260928-approved/`.

The user approved the exact 10,826 proposed contract/date exclusions. The new
policy preserves the five previously approved pairs, totaling 10,831. It is a
finite retrospective research exclusion, not historically known eligibility.
It does not change calendars, rerank contracts, invent terms/returns, or close
held positions into cash. Earlier raw records and policies remain intact. The
compiled identity is `bb5adfdf85b8de6f552a2e3feb0279783be1d44b786a1dc7ab200ed011633e57`.
The prior proposal/audit correctly retain their original pending-approval flags;
the separately bound approval and compiled policy establish the new decision.

Entry exposure is 7,237,976 original proposals (about 0.91% of 793,394,264),
626,091 distinct selections and 26,352,077 proposal/target rows across 299
securities. This is entry impact only. The new wave writer counts entry versus
held/roll exclusions separately; actual held crossing census remains unfinished.
Twenty-two reviewed rename corrections remain wired into the reference consumer.
New held dates can still require additional reference acquisition/adjudication.

## Full-scope execution preparation and bounded discovery

`plan_v7_full_execution.py` traverses all 591 securities and all frozen 5/15/30
proposal stores. It groups identical execution horizons while preserving their
original proposal multiplicities. Targets are expanded during replay, avoiding
a fivefold queue copy. Atomic per-batch checkpoints and sealed per-security stores
allow execution to begin before the entire queue is prepared.

`IndexedContractReferences` queries the disk census and lazily verifies raw packs.
`ReplayClocks` shares immutable minute clocks. Versioned replay/frontier files
preserve original execution semantics and the source hashes of earlier artifacts.
Execution cohorts share only proven identical pre-roll prefixes; earlier exits
retain their own replay. Membership hashes allow independent reconstruction.

Measured evidence:

- AAPL queue: 2,799,733 proposals became 1,150,180 distinct horizons in 58.61 seconds.
- Independent flat pilot: 5,000 horizon/target paths in 41.30 seconds; 1,021
  completed outcomes, 55 observed unfilled entries and 51 distinct missing inputs.
- Cohort pilot: 3,535 horizon/target paths, 826 buckets, 495 retained payloads;
  696 completed outcomes, 55 unfilled and 2,784 pending. All 3,535 reconstructed
  outcomes matched independent replay exactly, including fills, marks and gaps.
- Audited parity: `nn_meta/validation/v7-execution-wave-parity-20260928/`.
  Preserve stopped pilot `v7-execution-wave-20260928-r0` and flat
  `v7-full-execution-discovery-20260928-r3`; their SQLite hashes are bound.
- Exported/captured 43 actual missing windows (1,416 seconds), adding 203,821 bytes.
  `v7-full-wave-frontier-20260928-r0` binds the request scope;
  `v7-frontier-quote-index-20260928-r4` preserves all previous indexed intervals.

The campaign schedules bounded ten-minute process slices fairly across available
security queues, with two autosized workers, 5/6-GiB memory high/max, CPU 200%,
no swap and an eight-hour deadline. It emits actual input requests; it does not
automatically finish every capture/replay epoch. Shared physical settlement and
full-universe assembly remain later integrations, with their original evidence intact.
The 20-GB generated-state cap and 20-GB free-space floor bound this controller.
A separate compactor removes only verified equivalent generated scratch copies
once an immutable queue is sealed; it never deletes retained proposals or captures.

At 22:38 Central the selected r1 campaign had covered 327,795 horizon/target
paths and retained 263 pending requests, with no worker failures. The queue
had reconciled 200,081,158 proposals across 128/591 securities.
[Retained observation](2026-09-28-v7-full-discovery-observation.json).

Exact running pointers and dated observations belong in
[CURRENT_STATE](../CURRENT_STATE.md#v7-full-universe-execution-discovery).

## Validation and continuation boundary

Forty-six focused tests passed (two existing protobuf deprecation warnings).
A real frozen AAPL proposal selected the approved missing contract and produced
an explicit entry exclusion, no replacement/fills, no pending request and no
numerical label: `v7-approved-exclusion-consumer-20260928/`.
Focused tests cover queue census/resume, reference lookup, clock/replay parity,
shared-prefix boundaries, payload reconstruction, cohort membership, safe scratch
compaction, and exact approval binding. Original blackout tests exercise entry,
held and roll exclusions with retained fills and no fabricated labels.

Next: finish the full queue and initial discovery; capture only verified missing
windows from stopped checkpoints; rerun against a new frozen quote/reference
index; reconcile every proposed path disposition, held exclusion, provider failure
and retained byte. Continue until the declared 7-3 evidence is complete. Do not
convert a discovery checkpoint or this review into gate closure or a training receipt.
