# Handoff — v6 capture intake CLI; actual inputs still required

September 6, 2026, Chicago. Work remains on `main` in the primary checkout.
The user asked to read the expanded milestone and code what is needed to start
the v6 freeze. Launch is already authorized once the real input gates pass.
**The expanded freeze has not started.** Actual TradingView captures, exact
per-symbol context and full historical option-tick coverage remain required.
No source parity, evaluated model or deployment is claimed.

## This session

- Added `scripts.prepare_v6_parity_pack` with preview-by-default `prepare` and
  `verify` commands. Preparation derives all thirteen scopes, 127 raw fields,
  44 proposal events, source/default/runtime identities and terminal-snapshot
  requirements from the existing contracts. Review attestations remain blank
  or false; file hashes remain blank. The generated draft cannot pass admission.
- Verification requires a separately recorded pack SHA256, reruns the existing
  aggregate comparator, retains its complete report and writes a completion
  manifest last, after checking evidence/runtime hashes again. Fresh output
  directories only; symlinked outputs and overwritten evidence are refused.
- Generated a local draft at `/tmp/v6-capture-intake-20260906/` using minimum
  tick 0.01, source-literal sessions and observed VWAP. This is preparation,
  not actual data. Confirm the actual instrument settings when capturing.
- Added CLI regression coverage and documented commands in
  [V6_EXPANDED_INPUTS](docs/specs/V6_EXPANDED_INPUTS.md). Focused CLI/admission
  tests passed: 47. Full suite: **1,401 tests and 18 subtests passed**, 11
  warnings in 58.32 seconds. Diff and freeze-launcher shell syntax checks pass.
- Asked whether chart exports or reviewed/compiled harnesses exist and where
  they are stored; no reply had arrived when this handoff was written.

## Next required work

Obtain actual reviewed/compiled TradingView outputs. Populate the generated
pack with retained CSVs, metadata, local-producer sidecars where required,
instrumentation evidence and actual reviews. Include active numerical states
and all proposal events; POC/Footprint require terminal snapshots. Verify the
pack through the new CLI. Draft templates and synthetic tests are never parity
evidence, and a passing pack alone is not complete freeze admission.

Then materialize exact symbol context, run `scripts.plan_v6_option_requests`,
capture and verify every required tick window, materialize stores and seal a
new final expanded input manifest. Run preflight and the existing full launcher
only when these gates pass. Keep all twenty families and all 106 added columns.

## Preserved state

The prior expanded implementation, selected-contract tick sample, stopped core
pilot and operational boundaries remain as recorded in the
[previous handoff](handoff-history/HANDOFF-2026-09-06-before-parity-intake-cli.md)
and [milestone](docs/reviews/2026-09-06-expanded-v6-milestone.md).
The old untracked `nn_meta/artifacts_v6/` partials remain untouched.
Do not resume the stopped `raw-options-20260906-r2` campaign with new source,
reuse old artifacts, or run the generic notification-capable dispatcher.
No downloads, model training, server changes, notifications or trading actions
were performed in this session.
