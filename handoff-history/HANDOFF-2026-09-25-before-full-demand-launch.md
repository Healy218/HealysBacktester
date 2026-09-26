# Handoff — 2026-09-25 — V7-3 demand scheduler validated

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-25-before-demand-scheduler.md`.
Main is operational. Extensive unrelated dirty/untracked work predates this
session; preserve it and stage only owned changes.

## Current stage: V7-3

V7-1 and V7-2 are complete. Keep the 591-security, 1,773-store catalog at
`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30` unchanged.
The complete daily context remains `v7-daily-context-20260925-full`, with
667,239 rows and 1,182 passing raw-input prefix replays. The completion gate
is `nn_meta/validation/v7-2-completion-20260925`. Never overwrite the original
catalog-only `v7-2-final-deep-gate-20260925.json`; later evidence binds its hash.

## New completed milestone

`scripts/run_v7_entry_demand.py` implements the resumable scheduler with
one inner thread, 1–4 configurable outer workers, a process lock, immutable
per-security checkpoints, logs and atomic stage-specific `progress.json`.
It defaults to read-only planning; `--run` is required for generation.
The completion gate supplies the full 591-security scope. Explicit
`--security-id` values select validation cases, never redefine completion.

Its downstream feature view admits only the exact 415 reused-security and
ten additional historical-loader proofs. It verifies the deep-audited
feature/proposal receipt pairs, runtime, every input and the two exact
old/current source-hash pairs. Historical declarations remain bound unchanged;
new demand binds current sources plus the proof files. Strict producer/reader
code and all frozen stores were left unchanged. Do not edit the new scheduler
source casually: completed demand binds its hash.

Four cases completed under a 2 GiB stage budget with two outer workers:
- BBG004FPTZB8: current-loader MTUM; byte-identical SQLite to the original pilot.
- BBG010FXVQ98: original 415-security reuse proof with actual demand.
- BBG000B9YJ35: additional ten-security loader proof.
- BBG000BF8TF5: zero proposals; all 8,451 variants retained, zero requests.

Total: 97,935 proposals; 7,674 requests; 6,700 union capture windows across
139 contracts. Retained 11,000 no-contract and 75 no-fresh-price target outcomes.
All 12 demand/export/checkpoint receipts were unchanged on a real rerun.
SQLite integrity, censuses, links, clocks and export membership passed.
Output is about 37.5 MB; no provider downloads occurred. Four securities
are validation evidence only. Full request union and full-path scope remain open.

Outputs: `nn_meta/validation/v7-3-scheduler-20260925`.
Independent audit: `nn_meta/validation/v7-3-scheduler-validation-20260925`.
Review and commands: `docs/reviews/2026-09-25-v7-3-demand-scheduler.md`.
Full suite: **2,405 tests, 18 subtests, 20 warnings**. Four focused scheduler
regressions passed. No background V7 builder remains running from this session.

## Next concrete work

Establish a full-run demand storage forecast and total-project allocation,
using actual catalog scope/decision counts rather than extrapolating the sparse
validation subset. The allocated project footprint measured 421,285,347,328
bytes (about 421.3 GB); the older roughly 230 GB figure is stale. Then schedule remaining securities under that allocation,
reuse completed checkpoints, and reconcile the full union before capture.
The scheduler has a required stage-byte budget and preserves at least 100 GiB
free disk. Interrupted security work is preserved as partial evidence; completed
securities are verified and reused. It resumes at security boundaries, not
within a half-written SQLite database. Budget accounting includes partials.

After full entry demand: resolve dated option class hours and standard contract
references; derive and capture entry fills, minute marks, exits, rolls and
applicable stock-delivery windows. Keep the 250 GB acquisition ceiling.
Pre-decision feature requests alone never establish V7-3 completion or readiness.
The original catalog meter remains 1,773/1,773; use the new progress JSON for 7-3.

## Other work carried forward

V6 Alpaca fresh scanning and submission remain disabled. No broker orders have
been sent. Next: prospective scanner integration, bridge preview and multi-roll
lifecycle checks; never import the old simulator's positions. Keep simulator
and broker P/L separate. V5/V6 read-only incubator is enabled; its September 25
scheduled run still needs checking. Massive subscription decision is due
October 2; older historical option capture and V6 feed parity remain evidence
requirements. No V6 or incubator runtime was changed in this session.
