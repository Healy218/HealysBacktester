# CLAUDE.md

Durable facts for working in this repo. Live state (what's running, what's
broken today, current run verdicts) lives in the session memory files, not
here — this file should only need editing when the *setup* changes.

New to the project: `README.md` for what it is, `ROADMAP.md` for how the
phases fit, then `V4_OUTLINE.md` for current work.

## Environment

- **Repo**: `/home/healylabs/Coding/HealysBacktester`
- **Python**: `./venv/bin/python` (3.12.3). There is no conda, no system-python
  path — always call the venv binary explicitly.
- **Tests**: `./venv/bin/python -m pytest tests/ -q` — 345 tests, all green.
  They must not require LightGBM, network access, or v31 artifacts.
- **Secrets**: `.env` at the repo root, never in git. Keys: `ALPACA_API_*`,
  `MASSIVE_API_KEY`, `MASSIVE_FLAT_FILES_API_*`, `ALPHAVANTAGE_KEY`,
  `FINNHUB_API_KEY`, `REDDIT_CLIENT_*`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `FA_SKIP_COLLECTORS`.
- **`NN_META_POOL`** selects the strategy pool AND suffixes every artifact dir
  (`nn_meta/config.py`). Defaults to `v2`; the v3.1/v4 launchers export `v31`.
  Setting it wrong silently reads and writes the wrong directories.

## The box

i5-11400F (6C/12T, **no iGPU**), 16 GB DDR4 @ 2400, RTX 3060 Ti, Pop!_OS on
kernel 7.0.11. **It has an unresolved hardware fault that corrupts kernel
memory and freezes the machine**, most often under mmap-heavy dev tooling.
Commit and push often; don't leave hours of work uncommitted. Details and
everything already ruled out are in the `home-box-memory-corruption` memory —
read it before re-testing anything.

## Layout

- `nn_meta/` — the options meta-labeling pipeline (current center of gravity)
- `v3/`, `nn_options_signal/`, `fa/` — v3 pool, signal layer, fundamentals
- `scanner/`, `portfolio/`, `signals/`, `indicators/` — layer-1 vectorbt sweeps
- `scripts/` — launchers, watchers, reboot-recovery dispatcher
- `deploy/systemd/` — home-box systemd units (committed, not folklore)
- `tests/` — pytest suite

## Conventions

- Work on `codex/v4-causal-validation`. Small, single-purpose commits.
- **Scripts derive their own repo root**:
  `cd "$(dirname "$(readlink -f "$0")")/.."`. Never reintroduce an absolute
  local path — that's what broke every launcher when the WSL2 box was retired.
- **Never hardcode worker/shard counts.** Source `scripts/lib/autosize.sh` and
  call `autosize_workers <per_worker_mb>`; it divides MemAvailable (less a 2 GB
  reserve) by the budget and caps at `nproc`. The desktop is a real competitor
  for RAM here — with VS Code open the correct answer can be *lower* than the
  old hardcoded constants.
- Long jobs register with `scripts/boot_restart.sh` by creating an **empty**
  marker in `scripts/.jobstate/` at launch and writing the exit code at the
  end. Absent marker = never started here = leave alone.

## Traps

Things that look wrong and are not — check here before "fixing" them:

- `BASE=/home/mrhea/HealysBacktester/...` and `SERVER=mrhea@62.238.20.66` in
  `scripts/` are **remote** paths on the Hetzner box, where the user really is
  `mrhea`. Correct as written.
- `scripts/jobs.d/*.sh` are **sourced**, not executed. Their missing executable
  bit is correct.
- `nn_meta/HANDOFF.md` is a historical v2.2 record and tells you to run
  `wsl --install`. Ignore it; there is no WSL here.
- Run logs are written to the **repo root**, not `logs/` — `.gitignore` covers
  them with an anchored `/*.log`.
- `scripts/.jobstate/` and run logs are gitignored, so on a fresh checkout every
  job looks "not done". That is why the absent-marker guard exists.

## Deploy

Production is the Hetzner server (live scanner + FA collectors) — see the
`hetzner-server` memory. Deploy there by `git pull` over the deploy key, never
by scp: an untracked scp'd file once wedged pulls for days.
