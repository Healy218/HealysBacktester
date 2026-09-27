# Project instructions

HealyLabs is an ongoing MLOps research lab for options-trading models and
specialist researchers. Its mission is open-ended; each selected milestone has
finite scope, evidence and an exit condition. The user sets priorities.

## Document ownership

| File | Owns | Does not own |
| --- | --- | --- |
| `AGENTS.md` | Working rules, documentation ownership and session protocol | Session status or old continuation orders |
| `README.md` | Lab purpose, architecture and navigation | Live service names, flags or task status |
| `ROADMAP.md` | All workstreams, dependencies, phase gates and completed milestones | Detailed session instructions or volatile counters |
| `TODO.md` | Current phase's actionable checklist; explicitly separated operating deadlines | Independent future-workstream backlogs |
| `HANDOFF.md` | Last session's changes, stopping point and next actions | Copied histories, full runbooks or a competing task queue |
| `docs/CURRENT_STATE.md` | Exact selected artifact/service locations, configuration references and dated observations | New priorities, acceptance requirements or inferred live health |
| `DOCUMENTATION.md` | Durable conventions, traps and operating procedures | Running-job announcements or completed-work queues |
| `GOALS.md` | Dated maturity assessments and assessment criteria | Phase priorities or automatic score increases |
| `docs/DECISIONS.md` | Dated decisions, scope changes and rejected alternatives | A second current plan |
| `docs/EXPERIMENTS.md` | Evaluated runs, verdicts and evidence boundaries | Current operations or task ordering |
| `docs/specs/`, `docs/reference/`, `docs/reviews/` | Technical requirements, reference details and dated evidence | Instructions to reopen completed work |
| `handoff-history/` | Historical snapshots | Current instructions |

`CLAUDE.md` is a pointer to this file. Legacy FA planning files and the former
V7 state-page path are navigation pointers, not independent authorities.

## Session protocol

1. Read `TODO.md`, then `HANDOFF.md`. Consult the relevant roadmap gate for
   direction and only the relevant state/reference sections for exact inputs.
   Do not reconstruct the entire project from historical notes each session.
2. Work on `main` in `/home/healy/Coding/HealysBacktester`. Preserve unrelated
   dirty/untracked work. Make small, single-purpose commits and push completed
   work. A commit does not itself deploy or start a campaign.
3. Use `./venv/bin/python` explicitly. Run checks appropriate to changed behavior;
   the regression command is `./venv/bin/python -m pytest tests/ -q`.
   For documentation-only changes, verify links, ownership and consistency.
   Do not repeat training, capture campaigns or broad tests without a relevant
   change, failure or explicitly required check.
4. At session end or a milestone, archive the previous `HANDOFF.md` under
   `handoff-history/HANDOFF-YYYY-MM-DD[-slug].md` before writing a fresh handoff.
   Aim for about 60 lines: focus, changes, stopping point, next actions, relevant
   links and exceptional constraints. Do not append the old handoff body.
5. Update the owning documents together: TODO for task closure, ROADMAP for
   milestone status, CURRENT_STATE for selected pointers, DECISIONS for real
   decisions, EXPERIMENTS for actual evaluated verdicts. Commit and push the
   scoped result. A new checklist is not an evaluated experiment.

## Status and completion rules

- Use stable gate/task IDs from ROADMAP/TODO. Distinguish implemented components,
  full-scope validation, deployment, and measured outcomes. One does not imply
  the next. Keep dated observations labeled with their scope and timestamp.
- A gate closes against its declared deliverable and linked evidence. Completed
  work stays complete unless a specific defect or approved scope change
  invalidates named evidence. Record the reason and affected scope before
  reopening it. An old unchecked box or stale checker flag is not that reason.
- A new user direction takes precedence. Otherwise use each document for the
  facts it owns. Conflicting current evidence must be resolved explicitly;
  neither the newest filename nor a blanket 'latest text wins' rule proves it.
- Current state pages identify where to inspect live receipts. Their last
  observations do not establish that a process is healthy now. Archive old
  observations rather than carrying multiple purportedly current values.
- Reference/specification requirements are consulted for the selected gate;
  historical commands and prospective designs are not new execution requests.
- Keep FA and other workstreams in the main roadmap. Select their actionable
  work in the main TODO when authorized; maintain one cross-project handoff.

## Non-negotiables

- Point-in-time inputs, frozen artifacts, provenance and baseline comparisons.
  Never relabel an old artifact to bypass a contract check. Version changes and
  preserve existing checkpoints. Experts need their own admission gates.
- Read [DOCUMENTATION](DOCUMENTATION.md#traps) before concluding a script/cache
  is broken. Environment, deployment and provider details live there or in the
  current-state index, not in historical continuation instructions.
- Scripts derive their repo root (`cd "$(dirname "$(readlink -f "$0")")/.."`);
  use `scripts/lib/autosize.sh` for worker sizing, not hardcoded worker counts.
- `NN_META_POOL` selects both the strategy pool and artifact namespace. Verify
  the intended runtime manifest/configuration before using a launcher.
- Secrets remain in the untracked root `.env`; never print or commit them.
- Deploy server changes by `git pull` over the deploy key, never `scp`.
  Preserve isolation between research, paper accounts and live experts.
