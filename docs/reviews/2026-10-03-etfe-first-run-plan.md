# ETFE first-run planning and documentation reconciliation — October 3, 2026

The user requested the complete plan from the present VWAP setup through a
working expert with a completed build/freeze/train run, and asked that notes
follow the project ownership rules. This review records documentation work,
not a launched campaign, evaluated experiment or completed future gate.

## Recorded plan

[ROADMAP](../../ROADMAP.md#etfe-first-run-sequence) now owns ten ordered steps
under the stable ETFE-0 through ETFE-5 gates: contract, early resource pilot,
acquisition/input freeze, causal strategies/features, execution/labels, full
build/restart proof, dataset/experiment freeze, training, evaluation/model freeze,
and clean-process expert proof. The resource gate is explicitly cross-cutting;
its pilot precedes bulk capture/build and its final admission precedes training.

[ETFE_FIRST_RUN](../specs/ETFE_FIRST_RUN.md) defines the technical completion
evidence, source/feature/execution/evaluation contracts, distinct freezes,
initial finite training design, coverage and trial censuses, and expert reload/
replay requirements. Baseline/model design references V7 methodology without
reusing V7 weights, schema identity, provider configuration or old date boundaries.
Negative performance can finish a valid experiment but cannot earn promotion;
data/causality failures still prevent technical completion.

## Ownership reconciliation

| Owner | Update |
| --- | --- |
| ROADMAP | Full ordered plan, dependencies, stable gate/task IDs, deliverables and exit conditions |
| TODO | Current ETFE-0 feature/execution/evaluation/acquisition contract tasks only; later tasks remain in roadmap |
| HANDOFF | Fresh stopping point/next actions; previous body archived verbatim |
| CURRENT_STATE | Links to plan/acceptance; existing selected setup retained; future build/train/freeze artifacts explicitly absent |
| docs/specs | Technical first-run acceptance and navigation from ETFE scope; frozen JSON contracts unchanged |
| docs/DECISIONS | Dated first-run milestone/ownership decision; unrelated existing edits preserved |
| DOCUMENTATION | Durable preparation/input/dataset/model-freeze lifecycle and recovery conventions |
| README / setup reference | Navigation and distinction between existing setup CLIs and future unimplemented launchers |
| GOALS | Component-only evidence classification; no automatic maturity increase |
| docs/EXPERIMENTS | No new entry: no model evaluation occurred; unrelated working-tree content preserved |
| AGENTS / CLAUDE / history | Working rules/pointer unchanged; history preserved, no old task reopened |

## Verification and limits

Checked changed-document relative links/anchors, task-ID ownership and selected
artifact references, and confirmed prior HANDOFF/TODO snapshots match the
pre-edit content. The frozen VWAP and original midpoint setup integrity checks
still pass. No producer/config JSON, dataset, model, service, archive or provider
request was changed by this planning session. Documentation checks replace code
regression tests because there was no implementation change.

The existing 46-test component result remains dated prior evidence; it is not a
new end-to-end test. No duration or storage forecast is promised before the
measured pilot. Other workstreams and V7 research remain paused under their
existing boundaries. This planning commit does not imply deployment or launch.
