# V7 required-input continuation — September 30, 2026

The user selected completion of **all of 7-3**, without returning merely because
one capture/replay slice finishes. The runtime now continues across finite
checkpoint slices with **no overall cutoff**. Gate closure still requires the
declared full-scope evidence; supervisors never turn a partial receipt into closure.
[Reconciliation and dated observations](2026-09-30-v7-frontier-continuation.json).

## Reconciled actual frontier

The completed September 29 pending replay's 93 wave databases reconcile to
129,873 distinct requests: 129,300 quotes and 573 dated contract references.
Subtracting per-security sealed coverage and losslessly unioning requests leaves
126,719 quote windows. An independent cumulative-base overlap check found zero
already captured intervals. All 573 reference pairs were absent from the previous
reference epoch. This is actual replay demand, not a first-leg download envelope.

Reference capture and independent audit finished at **11:21:57 Central**:
573/573 standard responses, zero 404s, zero nonstandard contracts, 30 packs and
797,737 retained bytes. New epoch `v7-reference-epoch-20260930-r0` contains
2,226,402 original responses, preserves two exact-list admissions and leaves the
approved 10,835-pair exclusion policy unchanged. All 573 new pairs and both
previous alternate admissions passed reader readback. Earlier raw evidence remains.

Next frozen pending plan: `v7-pending-replay-plan-20260930-r0`, 93 securities,
241,944 cohorts, 1,091,170 selected cohort/targets and 20,729,596 horizon-target
evaluations. This queue is distinct from the already completed frozen replay.

## Continuous runtime

Initial quote capture began 11:21:13; original discovery resumed 11:21:18.
They retain their original six-hour checkpoint slices. Two controllers started
11:32 and wait for these exact services before continuing, avoiding overlapping
writers. Slice expiration no longer ends the selected work.

- `healys-v7-required-discovery-20260930.service`: resumes the original unchanged
  recovery controller until all 591 securities reconcile, preserving wave locks,
  successful cohorts and source contracts. CPU 100%, 3/4-GiB high/max, no swap.
- `healys-v7-required-frontier-20260930.service`: completes the current capture,
  replays its pending plan, freezes actual next requests, subtracts cumulative
  quote/reference coverage, captures/audits missing inputs and repeats. After
  the initial 93-security lineage finishes, it reconciles the completed full
  original discovery and follows that full-scope pending lineage. CPU 200%,
  4/5-GiB high/max, no swap. Capture worker ceiling two; replay ceiling one;
  reference I/O ceiling four; actual counts use `scripts/lib/autosize.sh`.

Both use Nice 15, existing free-space guards and a 6-GiB available-memory
admission floor. Low memory/disk availability waits rather than imposing an
overall deadline. Resource admission is checked before every child process.
V6's September 30 15:45 Central timer and market-hours guard remain unchanged.

Controller state: `nn_meta/validation/v7-required-inputs-20260930-r0/`.
`discovery/` and `frontier/` own bindings/progress; `epochs/<ordinal>/` retains
selections, raw snapshots, coverage reconciliation, captures, references, replay
plans and successor results. Producer/source changes require a new revision.
New reference failures, unsupported actual stock/calendar requests, integrity
errors and worker failures stop with their precise retained evidence for repair
or adjudication. They never become automatic exclusions or blind retries.

Fresh quote indexes have distinct paths on each continuation pass; old sealed
indexes are not overwritten. The v2 reconciler subtracts the *new cumulative*
coverage as well as the original wave's coverage and records reused references
by security/contract/date. Already captured references keep their real admission.

Only full original discovery, a successor lineage with no pending targets and
the completed finite MRHA migration allow a **closure candidate**. A candidate
still needs the full request/provider/storage/conditional physical-input review;
it is neither a gate-close receipt nor V7-4/training authorization.

## Verification and storage

Sixteen focused tests passed, including interval subtraction, security-specific
reference reuse, immutable epoch mismatch rejection, truthful terminal counters,
explicit failure handling and refusal to confuse the initial subset with the
full 591-security lineage. Launcher syntax passed. The current v2 real-data
pilot reuses 573 references while retaining exactly 126,719 quote windows.
No frozen producer was changed, and no broad training/regression run was repeated.

MRHA UUID 62C9-C390 was verified mounted read/write. Migration continues under its
existing service and catalog; measured observations are in the linked JSON.
No data was deleted, quota credited, source relabeled or model deployed.
