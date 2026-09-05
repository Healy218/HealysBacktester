# HANDOFF — state for the next session

Written 2026-09-04 ~04:00 UTC (2026-09-03 ~23:00 CDT). Protocol: `CLAUDE.md`.
Previous handoff: `handoff-history/HANDOFF-2026-09-03-v5-build-366-guard-and-box-workers-alive.md`.

## 2026-09-04 ~13:00 UTC update — cloud build ENDED, box finishing (user decision)

- Box is BACK (fresh OS; hardware trusted — user: ran 10 days clean, the
  faults were carried over from the old i5 build and are fixed). Restored:
  repo at `~/Coding/HealysBacktester` on `codex/v4-causal-validation`, venv
  (py3.12 via uv, 491 tests green), gcloud (creds survived), `.env`
  (Alpaca, Massive REST + flat-files, Telegram). STILL MISSING: Hetzner
  ssh key `~/.ssh/id_ed25519`, systemd user timers, FA collector keys.
- Overnight fleets drained to **426/441**; n2 fleet lost 11 tasks to spot
  preemption (us-central1-f/c), c2d fleet only got capacity at ~11:30Z.
  User ended both at ~12:40Z (`gcloud batch jobs delete`, both fleets).
- **15 stragglers**: AMKR APP ARM BA CELH CRWV DASH DECK DELL EAT ENPH
  FUTU GDXJ GLD GME. All but FUTU have family partials in
  `out/v5/meta_partial/`.
- `data_cache_v5` re-synced from the bucket (5.9 GB); preflight OK
  (500 day-frames, 0 missing).
- **`scripts/run_build_v5_local.sh` launched detached ~12:55Z**, 3 workers
  (autosize), log `logs/build_v5_local.log`; first builds GME + GLD. Check:
  `pgrep -af '[b]uild_meta_dataset'`; `grep -c published logs/build_v5_local.log`.
- **Reboot-safe (13:15Z)**: user unit `healys-build-v5.service` (enabled,
  linger on) relaunches the build at boot and disables itself when the
  script prints LOCAL-BUILD-DONE. Partials force-synced at 13:15Z. GLD
  published 13:14Z. After a reboot: `systemctl --user status healys-build-v5`
  then `tail -f logs/build_v5_local.log`. Resume this Claude session with
  `cd ~/Coding/HealysBacktester && claude --resume` (or `claude -c` from
  `~`, where this session was started).
- **17:07Z: build DONE 441/441 (16:55Z), marks audit CLEAN (all 441, 100%
  coverage, 0 orphans), ASSEMBLED on the box** (2,113,590 rows; marks 24.7M
  rows / 1.33M trades; train/val/test 1.37M/306k/442k) → published to
  `out/v5/meta_dataset{,.marks}.parquet`. `healys-build-v5.service`
  disabled itself. Determinism check (2× `--smoke --folds 1`, reports in
  `nn_meta/reports_v5/determinism/`) launched 17:02Z, log
  `logs/determinism_v5.log`. NEXT: if DETERMINISM-OK → full walk-forward
  on the box: `v4_evaluate --folds 3 --marks ... --seeds 0,1,2,3,4
  --epochs 60 --gbt-estimators 600 --embargo 1D` (v31 took ~3–4h on 8 vCPU
  at 489k rows; v5 is 4.3× rows on 16 threads, expect several hours+).
- **18:00Z: LADDER NEARLY DONE.** Determinism OK → walk-forward DONE
  (3 folds, ~21 min, all eligible, no negative fold; PBO 0.36/0.26/0.24
  after fixing the dropped-PBO report bug in `v4_evaluate.py` + test;
  rerun reproduced run 1 bit-for-bit; suite 510 green). Verdict entry
  written at the top of `docs/EXPERIMENTS.md`. Reports published:
  `out/v5/evaluate-20260904T173053Z-box/` and `…175907Z-box-pbo/`.
  **Finalize RUNNING** (launched 17:32Z; nn ev/0.05 selected, eligible,
  val +421.8%; 40-seed ensemble training into
  `nn_meta/model_final_v5.staging/` → `model_final_v5/`; log
  `logs/finalize_v5.log`). When it lands: append the finalize line to the
  EXPERIMENTS entry, publish `model_final_v5/` + reports to
  `out/v5/finalize-<stamp>-box/` with SHA256SUMS, tick TODO block 6.
  Deploying a v5 bundle is a USER DECISION (the live scanner reads
  `model_final_v4/`, which is untouched). Uncommitted: HANDOFF, TODO,
  EXPERIMENTS, .gitignore, v4_evaluate.py + test.
- **18:45Z: LADDER COMPLETE. Finalize REFUSED** (40-seed nn ev/0.05
  +201% vs ex-top3 bar +382% on the 2026-05-21→08-21 tail; nothing
  persisted; V118 untouched). Full reading + options in the EXPERIMENTS
  entry. Both reboot safety-net units are disabled. The only open item is
  the user's call on the next lever; no compute is running.
- **19:30Z: the finalize refusal is tie-order noise, not the model** —
  see the EXPERIMENTS entry's "bar dissected" paragraph and
  `scripts/gate_bar_sensitivity.py`. The ex-top3 bar re-draws to a median
  of −39% (range −66%…+283%) with only equal-timestamp ties shuffled; the
  refused ev/0.05 ensemble (+201%, maxDD 16%) clears 7 of 8. NEXT = user
  picks the gate definition (options a–d) → DECISIONS → code+test →
  re-finalize on the box.
- **23:30Z: (a)/(b)/(c) + confidence sweep DONE from one training** (code:
  `GATE_BAR` variants, `--report-all-gates`, `--thresholds`, finalize
  saves `finalize_val_predictions.parquet`; `scripts/policy_gate_sweep.py`
  sweeps everything offline in ~10 min). Results + recommendation (adopt
  (a) risk-aware; 0.45 never tried; ≥0.65 keeps nothing) in EXPERIMENTS.
  Still no v5 bundle — needs the user's gate decision, then
  `--gate-bar risk` finalize (~1h) persists nn ev/0.05 as-is.
- **00:50Z 2026-09-05: v5 BUNDLE EXISTS.** User adopted gate (a); finalize
  under `--gate-bar risk` → ELIGIBLE, nn×40 ev/0.05 persisted to
  `nn_meta/model_final_v5/` (gitignored; published to
  `out/v5/finalize-20260905T004700Z-box-risk-ELIGIBLE/` + SHA256SUMS).
  V118 untouched, nothing deployed, nothing running. Open: deploy
  decision (TODO block 6 last item); optional 0.45-threshold walk-forward.
- Then: audit marks coverage → assemble on the box (`--membership` ON, pull
  all row+marks shards first) → determinism check → evaluate/finalize.

## The one-paragraph state

**v5 dataset build: 393/441 rows and finishing in the cloud overnight,
unattended and unguarded — deliberately.** The home box is DOWN for
hardware repair (user, 2026-09-03 evening); its build workers and the
budget guard died with it. The user explicitly approved letting the two
GCP fleets drain on their own, accepting up to **~$20 on the card**
(credits were ~$5 at decision time; the account is paid). The fleets
self-terminate: verified via `gcloud batch jobs describe` that both carry
`maxRetryCount: 3` + `maxRunDuration: 8h` per task, so every task ends
and VMs deallocate when the queues drain. Expected residual cost ~$13.
The live V118 scanner on `main` is untouched.

## FIRST ACTIONS next session (in order)

1. **Ground truth on the overnight run** — never from memory:
   `gcloud batch jobs list --location=us-central1` and
   `gsutil ls gs://healys-backtester/out/v5/meta_rows/ | wc -l`.
   Expect both `marks-build-4cca795-122502` (n2) and `-122504` (c2d) in a
   terminal state and the row count near 441 (438 is the realistic max —
   3 tasks are permanently dead to exhausted retries; 2 of those FAILED
   tasks were already terminal on the n2 fleet at handoff time).
2. **Check what it actually cost** (console billing). Baseline: ~$5 of
   credits left at 2026-09-04 04:00 UTC, burn ~$1.00/hr for the 4 spot
   VMs. If jobs are still RUNNING well past ~17:00 UTC, something wedged —
   cancel them by name.
3. **Reconcile stragglers**: diff `out/v5/meta_rows/` against the 441
   symbols in `artifacts_v5_in/baseline_spec.json`; rebuild the gap on the
   box (free, ~5x faster per worker) once the box is trusted again.
4. **Memory validation DONE 2026-09-04: memtest86+ passed, 0 errors
   through 6 passes** (user ran it during the repair). The DDR5 is no
   longer "unvalidated" — the main risk gating box-trained bundles is
   retired. Still run the cheap determinism check once before the first
   production bundle (evaluate twice, identical seeds, diff
   `SHA256SUMS.txt`) — it catches non-RAM nondeterminism too and costs
   one extra evaluate run.
5. Then the standing ladder from TODO block 6: audit marks coverage for
   post-2026-09-01-00:33Z symbols (~8 + in-flight) → assemble on the box
   (`--membership` ON, pull ~1 GB of shards down first, watch the mark
   stream memory) → evaluate/finalize → verdict row in
   `docs/EXPERIMENTS.md`.

## What died with the box (do NOT assume these are running)

| What | Status at handoff |
|---|---|
| Box build workers (`run_build_v5_local.sh`) | **DEAD** — last log 2026-09-03 16:21 CDT; user confirmed not running |
| Budget guard (`cloud_budget_guard.sh`) | **DEAD** — last log 21:21Z; fleets ran unguarded ~6.5h before the user noticed; spend blew past the $32 cap the guard would have enforced (est ~$34 when checked) |
| In-session Monitors | gone with the session |
| Server dead-man + StockTwits timers | systemd user timers on the box — **also down while the box is down**; the Hetzner server itself is independent and stays up |

The server dead-man being down means server incidents page nobody until
the box is back. Worth knowing, not worth panicking over.

## Money

- Credits effectively exhausted: ~$5 left when the overnight decision was
  made; overnight drain lands the overage (~$3–9, ceiling ~$15 absent a
  pathological straggler) **on the card, with the user's explicit OK
  (2026-09-03 evening, cap ~$20)**. Do not re-litigate; do not extend.
- The guard's lesson stands: it is the only brake, and it lives on the
  box. Any future cloud spend while the box is down runs uncapped.
- Post-campaign cleanup still owed: stale Artifact Registry tags (real
  cost on a paid account). Keep `4cca795`.

## Standing warnings (carried forward)

- **Never `pkill -f` a pattern that matches your own watcher** — bracket
  trick: `pgrep -f '[c]loud_budget'`.
- Image `4cca795` is current; `submit.sh` refuses tags with no manifest.
- The 12 skipped-thin symbols are RESULTS; the spec's 441 is the universe.
- Freeze is DONE (453/453, spec at `artifacts_v5_in/baseline_spec.json`).
- Doctrine 2026-09-03: assemble + training run **on the box** (DECISIONS);
  the determinism check is the gate, doubly so after the hardware repair.

## Next campaign, first item

Unchanged: TODO block 6's universe read-path plan (derive sorted → read
filtered → scan the slice; 310x measured on `get_chain`). Prerequisite:
`derive_contracts` writes the parquet unsorted, so predicate pushdown
skips nothing until that changes.
