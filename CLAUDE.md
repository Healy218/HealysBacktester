# CLAUDE.md

Read this first, whoever (and whatever model) you are. This file holds the
documentation system and the durable setup facts. Live state is never in
here — it lives in the files below.

## The documentation system

| File | What it is | Your obligation |
|---|---|---|
| `ROADMAP.md` | **Overall goals** — every workstream, one map, phase-gated | Consult for direction; it feeds TODO.md |
| `TODO.md` | The **current phase's** task list | Read at session start; tick items as they land |
| `HANDOFF.md` | State left by the **previous session** | Read at session start; rewrite fresh at session end |
| `handoff-history/` | Archived handoffs, dated | Move the old `HANDOFF.md` here before writing a new one |
| `DOCUMENTATION.md` | Coding notes, conventions, **traps**, ops runbook | Check its Traps before "fixing" anything that looks wrong; add durable facts here |
| `docs/DECISIONS.md` | Dated decision log incl. rejected alternatives | Append on real decisions; don't relitigate entries |
| `docs/EXPERIMENTS.md` | Scoreboard: every generation's verdict | Add a row per evaluated run |
| `docs/specs/` | Design specs (V4_OUTLINE, FA_SPEC, …) — reference, not task lists | Detail lookup only |
| `docs/v31_run_history.md` | Archived chronology of the v3.1 era | History, not live state |
| `README.md` | What the project is, layer by layer | Onboarding |

## Session protocol

1. **Start**: read `TODO.md`, then `HANDOFF.md`. That's the whole context
   load — don't re-derive state from scratch.
2. **Work**: on `codex/v4-causal-validation`; small single-purpose commits;
   push often. Tests stay green: `./venv/bin/python -m pytest tests/ -q`
   (345, self-contained — no LightGBM, no network, no v31 artifacts).
3. **End** (or at a milestone, or before context runs out): archive
   `HANDOFF.md` → `handoff-history/HANDOFF-YYYY-MM-DD[-slug].md`, write a
   fresh `HANDOFF.md`, tick `TODO.md`, log any decision/verdict in
   `docs/DECISIONS.md` / `docs/EXPERIMENTS.md`, commit and push.

## Environment (the facts you need before running anything)

- **Repo**: `/home/healylabs/Coding/HealysBacktester` on the Pop!_OS home
  box. Production is the Hetzner server — deploy by `git pull` over the
  deploy key, **never scp** (ops runbook: `DOCUMENTATION.md`).
- **Python**: `./venv/bin/python` (3.12.3) — always the venv binary
  explicitly; there is no conda or system path.
- **`NN_META_POOL`** selects the strategy pool AND suffixes every artifact
  dir (`nn_meta/config.py`). Defaults to `v2`; the live scanner uses `v3`;
  all v3.1/v4 work needs `v31`. Wrong value = silently reading and writing
  the wrong directories.
- **Secrets** in `.env` at the repo root, never in git.

## Layout

- `nn_meta/` — the options meta-labeling pipeline (center of gravity);
  live scanner + v4 parity/state under `nn_meta/live/`
- `v3/`, `nn_options_signal/`, `fa/` — at-scale data layer, signal layer,
  ticker-discovery loop
- `scanner/`, `portfolio/`, `signals/`, `indicators/` — layer-1 vectorbt sweeps
- `scripts/` — launchers, watchers, reboot-recovery dispatcher (+ `jobs.d/`)
- `deploy/systemd/` — home-box units (committed, not folklore)
- `tests/` — pytest suite

## Non-negotiables

- Scripts derive their own repo root (`cd "$(dirname "$(readlink -f
  "$0")")/.."`); no absolute local paths, no hardcoded worker counts
  (`scripts/lib/autosize.sh`).
- Point-in-time everything; frozen artifacts; new complexity must beat the
  boring baseline before it ships (full standing rules: `ROADMAP.md`).
- Experts deploy **alongside** the live scanner, never swapped in before
  their gates pass; `main` stays the operational line.
- Before concluding something in `scripts/` or the caches is broken, read
  `DOCUMENTATION.md` → Traps. Several things here look wrong and are not.
