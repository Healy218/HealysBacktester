# V7-3 recovery and preserved freeze — September 25, 2026

The user asked to recover the interrupted session and confirm that the existing
freeze was already preserved. The September 25 decisions explicitly retain all
1,773 frozen stores and admit V7-3 through separate historical-loader proofs.
The current completion gate is `v7-2-completion-20260925`; the earlier catalog-only
gate remains unchanged, including its historical daily-context limitation.

## What survived

The launch and handoff changes were staged but uncommitted. They are now committed
as `d76c2e1`. All 1,773 feature/proposal summary receipt pairs still match the
original deep audit. All 546 completed demand checkpoint identities and their
referenced receipts match. An additional declaration audit checked 21,001,900
input bindings across 1,873,058 distinct bound files: zero input/source drift.
This recovery receipt is `nn_meta/validation/v7-3-recovery-audit-20260925`.
It does not claim a fresh full audit of every completed demand SQLite payload.
The consumer verifies those payloads when reusing each checkpoint.

The original demand service stopped with the user-session shutdown at 20:47:59
Chicago time. Its saved progress had 546 completed, four running and 41 queued,
with about 88.7 GB of output. Temporary service definitions did not survive.
The freeze, completed checkpoints and interrupted partial directories survive.

## Storage recovery

The original 200 GiB stage allocation no longer fits available free space while
retaining the 100 GiB reserve. No files were deleted and that guard was retained.
The new immutable `v7-3-demand-recovery-plan-20260925` binds the original census,
request bounds, catalog receipts and 546 completed checkpoints. It replaces
estimates for completed securities with their actual bytes and applies the
original row allowances to all 45 remaining securities, retaining the full
8 GiB working margin and counting existing partial evidence.

- Current project allocated bytes: 509,997,318,144.
- Existing demand logical bytes: 88,714,461,452.
- Additional stress forecast: 40,096,097,408 bytes.
- Total stage stress forecast: 128,810,558,860 bytes.
- Revised stage cap: **140 GiB**, or 150,323,855,360 bytes.
- Estimated free space after consuming that entire allocation: 127.23 GB,
  above the 107.37 GB (100 GiB) reserve.
- Existing non-stage project plus revised cap: 571.58 GB, below 640 GB.

The original 200 GiB plan and launch receipts remain historical evidence.
The separate 250 GB acquisition ceiling still applies to later captures.

## Exact kernel difference and admission scope

The initial unchanged-scheduler restart (`e69f575f2d514a5fa6fb3063c474d90d`)
passed the revised storage preflight, then failed closed while reusing its first
three checkpoints. All 546 demand declarations differ from the current runtime
only in this platform string:

`Linux-7.2.6-1-cachyos-x86_64-with-glibc2.44`
→ `Linux-7.2.7-1-cachyos-x86_64-with-glibc2.44`.

The user explicitly selected “Validate kernel compatibility and preserve all
originals.” Python, executable path, glibc, packages, source/input hashes and
all other runtime fields must remain exact. No broad kernel-version exception,
global runtime override, declaration rewrite or receipt relabeling is permitted.

`scripts/resume_v7_entry_demand.py` is a separate recovery consumer. It uses
the existing historical-loader proof and original demand producer. Its explicit
catalog view checks the exact kernel pair before applying every original
receipt/source/input check. The old scheduler and strict readers are unchanged.
New demand records the actual current runtime and binds this recovery source
and the sealed equivalence proof. Legacy checkpoints remain byte-identical;
new checkpoints additionally bind the recovery source and kernel proof.

The runtime exception is limited to consuming the saved catalog and producing
entry-feature demand. It does not authorize feature regeneration, training,
option captures or broader runtime compatibility.

## Replay gate and recovery command

The gate replays the same four established cases: MTUM/current-loader,
original 415-security reuse proof, additional ten-security loader proof and a
zero-proposal security. It requires byte-identical SQLite demand, equal complete
reports and byte-identical request exports. New replay declarations retain the
actual new runtime; original outputs stay untouched. Production requires all
four cases and a hash-verified proof at
`nn_meta/validation/v7-3-kernel-equivalence-20260925`.

```bash
bash scripts/start_v7_entry_demand_recovery.sh \
  --unit healys-v7-entry-demand-recovery-20260925 \
  --completion nn_meta/validation/v7-2-completion-20260925 \
  --output nn_meta/validation/v7-3-scheduler-20260925 \
  --storage-plan nn_meta/validation/v7-3-demand-recovery-plan-20260925 \
  --kernel-proof nn_meta/validation/v7-3-kernel-equivalence-20260925
```

The launcher autosizes at most four outer workers, one inner thread, CPU/memory
limits, no swap and AF_UNIX-only sockets. It checks proof, storage and original
declaration before launch. The recovery shares the original scheduler lock.
Progress is now under `v7-3-scheduler-20260925/kernel-recovery/progress.json`;
the original root progress records the failed strict-runtime restart. The new
meter first verifies/reuses completed checkpoints and consequently starts at
zero; it does not mean the 546 saved checkpoints were lost.

After all 591 demand checkpoints complete, audit the full request union and
storage before dated option references/hours and full execution-path captures.
V7-3 and readiness remain open. V6 and incubator runtimes were not changed.

## Validation result

All four real cases passed: 97,935 proposals, 7,674 requests, equal reports,
byte-identical SQLite files and byte-identical request batches. The sealed proof
binds 48,807 files, including original and replay evidence. No stored runtime
declaration was changed. Eight focused recovery/scheduler tests passed; the full
suite passed **2,411 tests and 18 subtests**, with 20 warnings, in 120.33 seconds.
Both launcher syntax and the real read-only recovery preflight passed.

## Resumed service

Service `healys-v7-entry-demand-recovery-20260925.service`, invocation
`9a07064bbccd4f91aedd75e46580fd3a`, was verified active/running. Four autosized
workers, 400% CPU, 14/16 GiB memory high/max, zero swap and AF_UNIX-only sockets
were observed. At the saved follow-up it had revalidated/reused
62 checkpoints with no failures. This is dated restart progress, not
the total saved-checkpoint count; all 546 legacy checkpoints remained unchanged.
Launch evidence: `nn_meta/validation/v7-3-recovery-launch-20260925`.
