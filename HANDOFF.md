# Handoff — 2026-09-25 — full V7-3 entry demand running

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-25-before-full-demand-launch.md`.
Main is operational. Extensive unrelated dirty/untracked work predates this
session; preserve it and stage only owned changes.

## Active work: V7-3

The user directed starting the next stage. The 591-security, 1,773-store
proposal catalog is already frozen. V7-1 and V7-2 are complete; this is the
full option-feature demand run, not a proposal refreeze or training launch.
Keep `v7-2-full-catalog-20260922-rebuild-5-15-30` and all earlier receipts
unchanged, especially `v7-2-final-deep-gate-20260925.json`.
The full daily context and 1,182 prefix replays remain completed evidence.

**Running service:** `healys-v7-entry-demand-20260925.service`.
**Invocation:** `27da05b253cb4f3893d222be3eb1a834`.
**Output:** `nn_meta/validation/v7-3-scheduler-20260925`.
The service was verified active/running. All 591 securities are selected;
130 had sealed at the recorded 21:56 UTC follow-up, no failures, about 2.51 GB
of output. Inspect current `progress.json`/`controller.log`; these numbers
are only a historical snapshot. The existing four checkpoints were reused.
The full scope has 793,394,264 proposals, so small early jobs give no full-run ETA.

Four outer workers, one inner thread, 400% CPU quota, 14 GiB memory high /
16 GiB maximum, no cgroup swap, nice 10, IO weight 25, AF_UNIX sockets only.
No provider capture or training follows automatically. Do not modify the
scheduler or any bound producer/input while this run is active.

## Storage and launch evidence

The read-only full census is implemented in `scripts/forecast_v7_entry_demand.py`:
27,576,105 timeframe decisions; 20,345,211 unique selection decisions;
101,726,055 target identities. The observed expiry inventory bounds requests
at 122,916,244; the conservative byte model gives 193.45 GB.

Stage cap: **200 GiB**. Total-project budget: **640 GB**. Existing project:
421.285 GB allocated. Launch free disk: about 344.47 GB. Keep at least 100 GiB
free; the scheduler conservatively stops on its stage/free-space guard.
This budget is for demand only. Plan actual option captures after measuring
the full union and remaining disk; the separate 250 GB acquisition ceiling
still applies. Do not infer actual captured volume from request counts alone.

Receipts:
- `nn_meta/validation/v7-3-demand-census-20260925/summary`
- `nn_meta/validation/v7-3-demand-storage-plan-20260925`
- `nn_meta/validation/v7-3-full-demand-launch-20260925`

Review and exact command: `docs/reviews/2026-09-25-v7-3-full-demand-launch.md`.
Launcher: `scripts/start_v7_entry_demand.sh`. It derives the repo root,
autosizes within four workers, verifies the storage plan and checks the
scheduler's read-only preflight before creating the service.
The transient service survives terminal closure but is not installed for
reboot startup. After reboot, rerun the launcher. For an existing loaded
unit, investigate failures before `systemctl --user restart` to resume.
Completed security outputs are verified and reused. Partial security evidence
is preserved/counts toward the budget; no automatic cleanup occurs.

Validation: **2,407 tests, 18 subtests, 20 warnings**, 112.47 seconds; two new
census regressions pass, Bash syntax passes, actual launch/resource limits verified.
The strict producer and proof-aware scheduler code were not changed.

## Next concrete work

Monitor the active run. If all 591 seal, audit the full request union and
missing/no-contract outcomes; check actual storage before provider capture.
Then resolve dated option hours and standard contract references and derive
entry-fill, minute-mark, exit, roll and applicable stock-delivery windows.
Entry-feature demand alone does not complete V7-3. V7-4 through V7-7 remain open.
The old catalog progress meter still reads 1,773/1,773; it does not track demand.

## Other work carried forward

V6 Alpaca fresh scanning and submission remain disabled; no broker orders.
Next V6 work: prospective scanner/bridge preview and multi-roll lifecycle
checks. Never import old simulator positions; keep simulator/broker P/L separate.
V5/V6 read-only incubator is enabled; its September 25 scheduled run still needs
checking. Massive subscription decision is due October 2; older historical
option capture and V6 feed parity remain evidence requirements. No V6 or
incubator runtime was changed during this demand launch.
