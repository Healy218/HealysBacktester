# nn_meta — machine handoff (run the walk-forward on the Windows box)

Move the v2.2 walk-forward from the MacBook (M4) to the Windows/RTX-3060-Ti
machine. The Mac runs freeze → dataset → train → **select** tonight; the
Windows box runs **walk-forward** tomorrow.

> **GPU reality:** the 3060 Ti will barely help. Walk-forward time is dominated
> by freeze + dataset build (vectorbt CPU sims + Massive fetches), not by the
> tiny MLP training (~27 min of ~15h). TF 2.16 is **CPU-only on native
> Windows** anyway. The switch is worth it only to free the MacBook — run it on
> CPU and don't chase CUDA. If you insist on GPU, WSL2 + CUDA is the only path.

## Strongly recommended: use WSL2 (Ubuntu), not native Windows
vectorbt/numba/tensorflow install cleanly on Linux; native-Windows numba builds
are a headache. In WSL2 every command below matches what we've been running.
`wsl --install` (once), then work inside the Ubuntu shell.

## Steps (tomorrow morning, AFTER select_meta finishes on the Mac)

### On the Mac (before you leave)
1. `git add nn_meta/artifacts/baseline_spec.json nn_meta/model_final/ensemble_config.json && git commit -m "v2.2 frozen spec + selected ensemble config" && git push`
   (walk-forward only needs these two small files from the run — NOT the 40
   trained models or meta_dataset.parquet; it re-derives everything per fold.)
2. Copy the data cache to the Windows box (see transfer options below).

### On the Windows/WSL2 box
1. `git clone <repo>` (or `git pull` if already cloned)
2. `python3.12 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
   (Windows-native venv: `py -3.12 -m venv venv` then `venv\Scripts\activate`)
3. Recreate `.env` in the repo root (NOT in git):
   ```
   MASSIVE_API_KEY=...
   ALPACA_API_KEY=...
   ALPACA_API_SECRET=...
   # optional, for live alerts later: PUSHOVER_TOKEN=... / PUSHOVER_USER=...
   ```
4. Put the data cache in place (see below).
5. Sanity check: `python -m pytest tests/ -q`  (should be all green)
6. Run it: `python -m nn_meta.walkforward_meta`
   - Redirect + background so it survives a disconnect:
     `nohup python -m nn_meta.walkforward_meta > wf.log 2>&1 &` then `tail -f wf.log`
   - The final per-fold table appends to `nn_meta/reports/meta_report.md`.

## Data transfer — two options

`nn_meta/data_cache/` is gitignored (too big for git). Move it out-of-band.

**Option A — full cache (~1.9 GB), recommended.** Copy the whole
`nn_meta/data_cache/` folder (USB drive / network share / rsync / cloud). The
walk-forward then runs fully offline — no re-fetch, no Massive quota use.

**Option B — minimal (~30 MB).** Copy only these 5 parquets into
`nn_meta/data_cache/`:
`underlying_15m.parquet`, `underlying_daily.parquet`, `contracts.parquet`,
`universe.parquet`, `surface_daily.parquet`.
The walk-forward will re-fetch option bars from Massive on demand (adds hours +
uses API quota; the transient-retry logic handles blips). Only worth it if you
can't move 1.9 GB.

> The `bars_15m/` (1.5 GB) + `bars_daily/` (240 MB) folders ARE the option-bar
> cache. Copying them (Option A) is what makes the run fast.

## Gotchas
- Run from the repo root; paths are pathlib-based (cross-platform).
- `logs/` and `data/cache/` are created on demand.
- If numba/vectorbt fail to install on native Windows → use WSL2 (see top).
- Nothing here needs the Mac after the copy; the Windows box is self-contained.
