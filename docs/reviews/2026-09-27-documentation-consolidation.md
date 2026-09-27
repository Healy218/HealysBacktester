# Documentation consolidation — September 27, 2026

The user approved the six recommendations to consolidate the lab's notes,
explicitly leaving V7-3 untouched. This is a documentation change only.
The lab remains an open-ended MLOps research platform; its selected work stays
in Phase 7, gate 7-3. No model result or gate completion is inferred from this
reorganization.

## Ownership and migration

| Recommendation | Implemented result |
| --- | --- |
| 1. One responsibility per document | AGENTS owns the instruction/ownership protocol; CLAUDE points to it. README is onboarding, DOCUMENTATION durable knowledge and GOALS the assessment ledger |
| 2. Restore the whole-lab roadmap | Main ROADMAP includes shared data, model research, execution, incubator, FA, Pine parity, SPX0, volatility, stacking, RL and platform dependencies; Phase 7 has seven explicit gates |
| 3. Consolidate FA planning | FA milestones are in the main roadmap; detailed requirements in `docs/reference/FA_CONTEXT.md`; old FA roadmap/TODO/handoff paths are pointers |
| 4. Rewrite the handoff fresh | Prior handoff archived; new handoff is 49 lines, with focus, changes, next actions and constraints, without the old body appended |
| 5. One owner for changing facts | Existing V7 state index consolidated into `docs/CURRENT_STATE.md`, adding scoped operational/FA pointers; former path redirects; no live job claims in onboarding/runbook |
| 6. Explicit completion and reopening | Stable gate/task IDs, declared deliverables and evidence links; reopening requires a named defect or approved scope change, with unaffected completion preserved |

TODO still covers the selected Phase 7 steps and explicitly separated operating
obligations. Deferred research does not become a V7-3 prerequisite. Existing
7-3 capture/reference/path/coverage obligations and accepted resource policy
were preserved; no new data or verification gate was added.

The index distinguishes home research, frozen V6 source, fresh paper state,
historical simulator, FA automation and server operation. It labels prior
observations as dated and does not claim a new health probe. FA clarification
preserves the distinction between older raw collection, newer daily snapshots,
eligible completed labels and monthly cohorts. Paper startup does not claim an
actual fill; Friday inference does not claim evaluated outcomes.

## Preservation

[Archive index](../../handoff-history/docs-2026-09-27-before-consolidation/ARCHIVE.md)
and its `archive-manifest.json` preserve exact pre-edit working-file bytes,
including existing local documentation changes. The old handoff is
[separately archived](../../handoff-history/HANDOFF-2026-09-27-before-doc-consolidation.md).

Historical technical notes, experiment verdicts, decision history and FA
requirements remain accessible. Archived files preserve their original relative
link text; the archive index explains their historical context. Compatibility
pointers preserve old current-note entry paths. No retrospective performance
verdict or numerical maturity score was altered.

Broad unrelated implementation changes remain outside this documentation commit.
Existing unrelated edits in DECISIONS and EXPERIMENTS remain unstaged; only the
new ownership banners and this session's decision are selected from those files.
Root onboarding/runbook/scorecard edits are within the user-approved consolidation
scope and their original working versions are archived.

## Verification

Check current-document local links/anchors, exact gate/task IDs, compatibility
pointers, handoff size, archive hashes and selected runtime/input path text.
Check that the staged change contains only documentation and its archive
manifest, and that pre-existing non-Markdown working changes remain unchanged.
Do not run capture, deployment, training or the application test suite for this
text-only change. Results from the completed documentation checks follow.


- 15 current documents checked; 124 local links/anchors resolve.
- 14 archived originals match their saved SHA-256 values, including the
  separately archived handoff and original dirty decision/experiment ledgers.
- All 35 selected V7 runtime/input pointer strings from the previous index
  remain in the consolidated index. No selected checkpoint was replaced.
- Exactly one Phase 7 row exists for each step 7-1 through 7-7. All five existing
  7-3 obligation categories remain explicit in TODO; legacy FA files contain
  no independent checklist. The fresh handoff is 49 lines.
- All 41 pre-existing modified non-Markdown working files matched their
  pre-edit hashes. All files selected for this consolidation are Markdown
  documentation or the archive's hash manifest.
- No runtime, capture, training or application test command was run. The check
  was a temporary read-only documentation consistency script; it does not add
  another permanent testing framework or a new research gate.

The final staged scope is 33 documentation/archive files. Current edited
Markdown passes the whitespace check. Two verbatim archived FA originals retain
their pre-existing blank line at EOF; these were intentionally not normalized
so their archive hashes remain exact. Unrelated decision/experiment edits remain
outside the selected change.
