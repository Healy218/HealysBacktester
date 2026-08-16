# TODO — current phase

**Phase: ship v4 as a second expert on the server** (`ROADMAP.md` ▶ NOW).
Set 2026-08-15; target: this weekend.

> **The standing goal (user, 2026-08-16): v4 goes to the server the moment
> it finishes training/building.** Deploy is the *immediate* next action
> once the bundle lands — nothing queued between re-finalize and deploy.
> Corollary: do block 2 (the live scoring path) **while** the dataset builds
> and the model trains, so it is never the bottleneck.

How this file works: it holds the tasks for the *current* ROADMAP phase only.
Work top to bottom, tick boxes here as things land, record mid-task state in
`HANDOFF.md`. When the phase exits, refill this file from ROADMAP's next
phase and log the exit in `docs/EXPERIMENTS.md`.

Everything below runs with `NN_META_POOL=v31` unless said otherwise —
without it the pipeline silently reads/writes the wrong artifact dirs.

## 1 — Finish v4 on the ledger (Option B, `docs/specs/V4_OUTLINE.md` stage 2)

- [~] **Mark-stream build RUNNING since 2026-08-16 02:42** via
  `scripts/run_build_parallel.sh` (now passes `--marks` and writes the
  `scripts/.jobstate/v31_marks_build.exit` marker; assemble folds
  `meta_marks/` into the `meta_dataset.marks.parquet` sidecar, ~88M rows /
  ~1.7 GB). Launched at 1 shard (desktop held RAM); **re-running the same
  script widens the shard count and resumes from per-symbol checkpoints** —
  kill the old launcher first (`pkill -f run_build_parallel.sh; pkill -f
  nn_meta.build_meta_dataset`). Stale July rows archived to
  `meta_rows.pre-marks-2026-08-15/` (they predate the provenance columns —
  a cached-skip rebuild would have emitted zero marks). Logs:
  `v31_marks_build.log` + `v31_build_<k>.log` at repo root.
- [ ] **Selection-side ledger wiring**: `evaluate_window()` /
  `choose_policy()` in `nn_meta/v4_evaluate.py` rank candidate policies on
  the `v4_accounting` mark-to-market ledger instead of
  `select_meta._portfolio_sim`. (`--marks` reporting path + fail-closed
  guards already exist; this is the selection swap.) Regression tests with
  synthetic fixtures, suite stays green.
- [ ] **Re-run through the ledger**: `v4_evaluate --ablation` and
  `--folds 3` (seeds 0-4, epochs 60, gbt 600, embargo 1D). Compare against
  the stage-0 tables in `docs/specs/V4_OUTLINE.md` — numbers are *expected*
  to move; log the new verdict in `docs/EXPERIMENTS.md`.
- [ ] **Re-finalize**: `v4_finalize` → fresh `model_final_v4/` selected and
  trained under the ledger. Also fixes the current bundle's unverifiable
  manifest (it predates hashed persistence). Persist is atomic + gate-checked
  by construction; the old bundle is additionally in the D: backup.

## 2 — v4 live scoring path (stage 5, closes the last gate item)

- [ ] **Live v4 scorer**: wire `nn_meta/live/v4_candidates.build_candidate_batch`
  (causal features from closed bars, no `prem_spot`, no option fill) +
  `nn_meta/v4_loader.load_final_v4()` / `ensemble_score()` into a scanner
  entry point for the v4 expert. Do not touch the deployed v3 scorer.
- [ ] **Parity test green**: `assert_candidate_parity` offline vs live-path
  features on the same bars — this is the 5th/last first-implementation gate
  item in `docs/specs/V4_OUTLINE.md`.
- [ ] **Expert-labeled alerts + own state**: v4 alerts carry a `[v4]` label
  next to v3's; v4 gets its own `PaperLedger` + alert dedupe/outbox from
  `nn_meta/live/state.py` (built and tested, needs wiring).

## 3 — Deploy to Hetzner (alongside v3, never replacing it)

- [ ] Ship the bundle: force-add `model_final_v4/` + its config (same pattern
  as the committed `model_final_v3/`) or transfer out-of-band — decide and
  record in `docs/DECISIONS.md`.
- [ ] Server: `git pull` (deploy key — never scp), v4 self-test that
  force-loads all seeds (mirror `_st.py`/scorer_selftest), add the v4 expert
  to the cron scanner pass, verify a Telegram alert end-to-end.
- [ ] Rollback documented in `DOCUMENTATION.md`: removing the v4 expert
  leaves v3 running exactly as today.

## Fallback if the weekend runs short

Deploy the **existing Option A bundle** as the `[v4]` expert in
paper/alert-only mode (labeled unvalidated-by-ledger), and let the Option B
re-finalize replace the bundle in place next week. Deploying alongside —
never swapping v3 — is what makes this safe either way.

## Parked (not this phase)

- PBO report wiring (needs the per-fold candidate matrix).
- Magnitude/EV head training on v31 data (`nn_meta/ev_sizing.py` is
  code-ready; joins the policy grid once trained).
- Fold-3 regime miss (noise vs real weakness): carried into the expert-panel
  phase, where per-expert forward tracking answers it empirically.
