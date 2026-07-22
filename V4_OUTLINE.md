# v4 Outline — Causal Validation and Research Reproducibility

Status: Stage 0 empirical results are in (2026-07-21 night, see below) —
v4's causal fixes (`prem_spot` removed, purged nested selection) confirmed
real: the corrected ablation is still solidly positive (not zeroed out by
the leakage fix), and the nested 3-fold walk-forward's winners are
broadly-diversified across symbols/strategies rather than outlier-dependent
the way the uncorrected v3.1 walk-forward was. A deployable candidate
(`model_final_v4/`, GBT/filter/thr=0.5, 40-seed ensemble) is trained and
persisted — Option A of the finalize plan. Option B (route evaluation
through the stage-2 mark-to-market ledger before trusting this further) is
partially wired: the reporting-side `--marks` ledger path shipped as queue
item 1, but selection-side routing, the ledger re-runs, and a re-finalize
are not started. Created from commit `5474335` on 2026-07-20;
causal-validation infrastructure was added on `codex/v4-causal-validation`
the same day.

2026-07-22: both machines' parallel work (MacBook queue items 1–11; Windows
box stage-0 runs + `v4_finalize.py` + reboot job system) merged cleanly at
`1189166` and an adversarial review of the merged state ran. **Fresh coding
session? Start at "2026-07-22 session queue" below** — the original
coding-session queue is complete (all 11 items [x]).

## Purpose

V4 is the next research generation of HealysBacktester. It preserves the v3/v31 proposal, options execution, and FA work while making the evaluation contract causal, reproducible, and directly compatible with the live scorer.

The v31 run may finish under the existing contract. Its outputs are useful for scaling and ablation diagnostics, but they are not promoted as final evidence until the gates below pass.

## Constraints

- Options history is approximately two years.
- Options bars are 15-minute aggregates.
- Underlying history is materially longer and may support longer feature windows.
- The present-day symbol universe is survivorship-biased until a point-in-time constituent source is available.
- V4 must not assume that historical option quotes, spreads, or delisted contracts can be reconstructed more precisely than the provider supports.

## Non-negotiable research rules

1. Every feature has an explicit `available_at` timestamp and must be available before the decision timestamp.
2. Initial option entries occur after the signal bar; exits use a separately specified actionable bar.
3. Splits are purged by both entry and exit timestamps, with an explicit embargo.
4. Model architecture, feature set, thresholds, DTE policy, and portfolio policy are selected inside temporal training folds.
5. Open positions are marked to market; returns, drawdown, exposure, turnover, and capacity are reported at portfolio level.
6. NN, GBT, baseline, and buy-and-hold comparisons use the same universe, folds, slots, costs, and exposure convention.
7. Every dataset, model, report, and cache is tied to a manifest containing code revision, config hash, feature schema, universe, coverage, and provider metadata.

## Coding-session work queue — start here (no v31 dependency)

This is the separated queue for a fresh coding session working while the
remote v31 model trains. Everything here can be fully coded and tested on
this machine with synthetic fixtures or already-local data; nothing needs
the remote `meta_dataset.parquet`. An adversarial review (Codex) follows
each session, so keep commits small, single-purpose, and specifically
messaged.

Session conventions:

- Work the queue top to bottom on `codex/v4-causal-validation`.
- Every item ships with regression tests; `./venv/bin/python -m pytest
  tests/ -q` stays green. Local tests must not require LightGBM, network
  access, or v31 artifacts (existing tests follow this rule — keep it).
- When an item is done, tick its checkbox here AND the matching checkbox
  in the stage/track sections below. This file is the single source of
  truth handed to the next session.
- Do not modify the deployed legacy v3/v31 scorer path, and do not relabel
  it as v4 parity (it still depends on `prem_spot`).
- Note: `v3/data/` (9y underlying) and `nn_meta/data_cache_v3` are NOT on
  this machine; only the legacy ~2y `nn_meta/data_cache` is local. Items
  touching deep history are coded against fixtures here and executed where
  the data lives.

### Queue

1. [x] **Stage 2 — mark-stream ledger plumbing.** `nn_meta/mark_stream.py`
   defines the sidecar mark-stream schema, a deterministic per-row key
   (`stable_trade_id`), IO, and the bridge into `v4_accounting`.
   `nn_meta/v4_evaluate.py` routes the winning policy's entered trades
   through the ledger when `--marks` is supplied (fail-closed / `pending`
   otherwise). Tested against synthetic fixtures; real streams attach when
   v31 data lands.
2. [x] **Stage 2 — fill-failure reason codes.** `nn_meta/v4_accounting.py`
   adds the `FillFailure` taxonomy (no entry/exit bar, zero bid, crossed,
   stale, wide spread), a conservative `FillPolicy`, `classify_quote`, and
   `resolve_fills` (entry failures reject the trade; exit failures book a
   conservative worst-case/intrinsic value). Every code path is tested.
3. [x] **Track 2 — fold-local probability calibration.**
   `nn_meta/calibration.py` provides pure-numpy Platt and isotonic (PAV)
   calibrators, Brier score, and a reliability table. `v4_evaluate` fits the
   winner's calibrator on validation predictions only and scores test; the
   report gains a calibration section. A regression test proves the mapping
   is invariant to test labels (never sees test rows).
4. [x] **Track 2 — deflated Sharpe / PBO utilities.**
   `nn_meta/multiple_testing.py` adds Probabilistic/Deflated Sharpe (stdlib
   `NormalDist`) and CSCV-based `combinatorial_pbo`, tested against analytic
   cases. `v4_evaluate` deflates the winner's test Sharpe by the full policy
   grid and reports it. (PBO utility is available; wiring it needs the
   per-fold candidate matrix — a follow-up.)
5. [x] **Backlog — score-decile diagnostic.** `nn_meta/diagnostics.py`
   emits per-decile mean score, win rate, and mean return, with a
   `top_decile_inverted` flag; `v4_evaluate` renders it (with a ⚠ marker)
   in every report. A test reproduces the v3.1 shape (win rate up, return
   down) and asserts the flag fires.
6. [x] **Backlog — magnitude head / EV sizing (code only).**
   `nn_meta/ev_sizing.py` provides the return-bucket magnitude labels and
   `bucket_expected_value` (the no-second-head path), `predicted_ev` (the
   two-head path), and an EV-weighted slot portfolio (`evaluate_ev`) that
   reduces to uniform when EVs are equal and only de-risks low-EV names.
   Pure and tested; joins the policy grid once a magnitude/EV prediction
   column is trained on v31 data.
7. [x] **Track 1 — HAR-RV/GARCH baseline module.**
   `nn_meta/vol_forecast.py` has realized-variance targets, HAR-RV (OLS) and
   GARCH(1,1) (scipy MLE), QLIKE + pinball losses, and one-step-ahead OOS
   evaluation under the stage-1 `expanding_folds`. Fixture tests pass; the
   smoke run on local daily SPY shows HAR/GARCH beating the naive constant
   variance. Full intraday-RV 9y run happens where `v3/data/` lives.
8. [x] **Stage 5 — live candidate-batch constructor.**
   `nn_meta/live/v4_candidates.py` builds a v4 causal candidate batch from
   closed underlying bars — reusing the offline `technical_features`,
   `join_surface_asof`, and one-hot maps — with no option fill (no
   `prem_spot`), so parity holds by construction. `assert_candidate_parity`
   wraps `v4_parity.assert_feature_parity`; tests cover schema, determinism,
   parity pass, and drift-detected failure.
9. [x] **Stage 5 — alert/outbox/paper-ledger state.**
   `nn_meta/live/state.py`: atomic (temp + `os.replace`) `AlertState`
   (idempotent dedupe), `Outbox` (at-least-once, key-deduped, ack lifecycle),
   `PaperLedger` (realized/unrealized P&L, equity), plus
   `population_stability_index` drift and `health_snapshot`. All rebuild from
   disk on construction; tests cover crash-safe reload and each guard.
10. [x] **Stage 4 — lockfile + CI.** `requirements.lock.txt` is a full
    `pip freeze` reproducibility snapshot; `scipy` is now explicit in
    `requirements.txt`. `.github/workflows/ci.yml` runs `pytest tests/ -q`
    on an ubuntu-latest + macos-latest / Python 3.12 matrix. (Locally the
    suite is green and self-contained; the remote matrix runs on push/PR.)
11. [x] **Stage 6 — FA score-table feed.** `fa/entities.py` implements
    precision-first entity resolution (cashtags + alias map, `valid_tickers`
    filter); `fa/scores.py` adds `resolve_mentions`, attention-velocity
    z-scoring vs each ticker's own trailing baseline, and `build_score_table`
    producing exactly the `{ticker, observed_at, source_family, score,
    evidence_ref}` table `universe_loop.monthly_rank` consumes. Tested
    end-to-end through a corroborated ranking.

### Blocked until remote v31 artifacts arrive — RESOLVED 2026-07-21 night

Historical note: this section gated the queue above while the v31 dataset
lived only on the Windows box. The stage-0 reconciliation runs and the
"First remote v31 run" commands are DONE (see stage 0), and
`meta_dataset.parquet` + `baseline_spec.json` are now committed, so the
MacBook can run the evaluator against real data too. Still genuinely
pending: real mark-stream emission, and the magnitude-head *numbers*
(training a head on v31 data — the labels are code-ready).

### Explicitly deferred — do not start

- Track 3 RL (requires the stage-2 ledger and a validated supervised
  policy as its baseline).
- Track 1 sequence forecaster (requires its classical baselines from
  queue item 7 to exist and be beaten).
- Track 4 sentiment scoring at scale (FA archive lives on the Hetzner
  server; only fixture-level plumbing belongs in a local session).

## 2026-07-22 session queue — start here

Source: the 2026-07-22 adversarial review of the merged overnight state
(every item below was independently verified against the code, not just
asserted). Ordered so correctness fixes land before the Option B re-runs
that depend on them.

1. [ ] **`choose_policy` eligibility fallback can crown gate-failers.**
   `choose_policy` falls back to `pool = eligible or candidates`
   (`nn_meta/v4_evaluate.py` ~line 173), so when every mode×threshold
   candidate fails `MIN_KEPT_TRADES`, the drawdown cap, or loses to the
   frozen baseline, a gate-failing policy is still returned as "winner" —
   and the cross-family pick (fold winner in `evaluate_window`, and
   `v4_finalize.py:174`) never reads `eligible`. This is the confirmed root
   cause of the local smoke walk-forward's -26.3% "winner". Fix: propagate
   an `eligible` flag through fold winners and reports, and make consumers
   (fold selection, finalize) treat ineligible-everywhere as "no config
   passed" rather than silently promoting the least-bad.
2. [ ] **`v4_finalize.py` operating point is unvalidated for the shipped
   ensemble.** Family/mode/threshold and the recorded `val_return` were
   selected with a 5-seed NN mean / single `random_state=0` GBT, but the
   persisted artifact is a 40-seed ensemble whose mean-score distribution
   differs — the deployed threshold was never evaluated with the model that
   ships. Fix: after training the final seeds, re-predict the validation
   tail with the full ensemble, re-run `choose_policy`, and persist the
   final-ensemble metrics (and fail if the re-check flips eligibility).
3. [ ] **`v4_finalize.py` destroys the previous bundle before the new one
   exists and skips the baseline gate.** `shutil.rmtree(FINAL_DIR)` runs
   before the ~40-seed training loop, and nothing mirrors
   `select_meta.py`'s "NO ELIGIBLE CONFIG — test untouched" refusal. Fix:
   train into a temp dir + atomic rename, gate persistence on eligibility
   (item 1), and extend the manifest to cover the trained models and
   ensemble_config, not just inputs.
4. [ ] **No loader can read `model_final_v4/`.** `select_meta.predict_rows`
   KeyErrors on a v4 scaler (indexes with legacy `META_FEATURES` incl.
   `prem_spot`), `resolve_run_dir` never looks in `model_final_v4/`, and
   nothing in the repo loads `model.joblib` at all — the actual persisted
   winner is GBT. The scoring convention (raw unscaled features +
   `predict_proba` for gbt vs fillna+standardize for nn) lives only in
   `v4_evaluate.py` source. Fix: a small v4 bundle loader
   (`load_final_v4()` + `score_rows()`), which stage-5 parity needs anyway.
5. [ ] **Reboot dispatcher hardening** (see "Reboot-recovery job system"
   below for what happened this morning): (a) unconditional run-log line +
   optional "dispatcher alive" heartbeat notification so a no-op boot is
   distinguishable from a dead scheduled task; (b) per-run done-markers
   (marker files tied to a run id, not `grep` of an append-only log — a
   stale `V4-EXIT:` from a previous run permanently disables restart of any
   re-run); (c) split success vs failure exit markers — today a job that
   ran and FAILED matches `JOB_DONE_CHECK` and is never retried; (d) commit
   the `schtasks` registration command as an in-repo artifact. Codeable
   here; the actual re-registration + real reboot test happens at the box.
6. [ ] **Calibration caveat before trusting reported calibrated numbers:**
   on all five local smoke runs isotonic *degraded* test Brier and mapped
   111 test trades to probability 1.0 (33% realized win rate) — small
   validation tails overfit isotonic's step function. Consider selecting
   the calibrator (Platt vs isotonic vs none) on validation Brier instead
   of hardcoding isotonic.
7. [ ] **Option B steps 1–3** (the selection-side ledger swap and re-runs)
   — see the corrected Option B plan in stage 2, including the 2026-07-22
   dataset constraint note. Runnable on either machine now that the v31
   dataset is committed.
8. [ ] **Windows-box evidence recovery (at the box):** the real stage-0
   reports + manifests and `model_final_v4/` exist ONLY on the Windows box
   — the outline's tables are currently the sole record of the headline
   numbers. Pull the merged branch there, commit the stage-0
   reports/manifests (small), and back up `model_final_v4/` before any
   re-finalize overwrites it.

## Reboot-recovery job system (added 2026-07-22)

`scripts/boot_restart.sh` is a generic dispatcher that runs at Windows
logon via the hand-registered "HealysBacktester WF AutoRestart" scheduled
task and relaunches any job in `scripts/jobs.d/*.sh` that is neither
running nor finished (see `scripts/jobs.d/README.md`; launchers:
`scripts/run_v4_v31.sh`, `scripts/run_v4_finalize.sh`). It replaced the
single-purpose `scripts/wf_boot_restart.sh` on 2026-07-21.

**2026-07-22 morning reboot test, diagnosed the same day:** the "auto-restart
did not fire" observation is most likely the dispatcher's designed no-op —
all three registered jobs (v31 walk-forward, v4 full run, v4 finalize) had
already written their done-markers before the reboot, so the correct
behavior was to restart nothing and send nothing. But the dispatcher writes
no log of its own invocations, so "ran and correctly did nothing" is
indistinguishable from "scheduled task never fired" (the logon *trigger*
path has still never been truly exercised — the task was only test-fired
manually). Queue item 5 above fixes the observability and the related
done-marker defects; until a logged real-reboot test passes, do not assume
crash recovery works.

## Stages

### 0. V31 reconciliation — DONE 2026-07-21 night

Ran on the Windows/WSL box against the real 118-symbol `meta_dataset.parquet`
(committed to `main` at `65c635c`, pulled via `codex/v4-causal-validation`).

**Ablation** (4 treatments, static window) — distinguishes schema leakage
from split leakage:

| schema | purged | test return | maxDD |
|---|---|---|---|
| legacy (`prem_spot`) | no | +136.6% | 15.0% |
| v4 (no `prem_spot`) | no | +45.2% | 25.5% |
| legacy | yes | +90.9% | 27.2% |
| v4 (fully corrected) | yes | **+72.6%** | 24.4% |

Removing `prem_spot` alone roughly halves the return (136.6%→45.2%) —
confirms it was genuinely leaking. The fully-corrected row is still solidly
positive: real signal survives, smaller than the leakage made it look, which
is the desired outcome (pipeline bug ruled out, strategy validity partially
confirmed).

**Nested 3-fold walk-forward** (v4 schema, purged, per-fold independent
family/mode/threshold selection — no single reused config):

| fold | winner | return | ex-top3 | % retained | maxDD |
|---|---|---|---|---|---|
| 1 | nn/filter/0.55 | +754.6% | +340.7% | 45% | 25.5% |
| 2 | gbt/filter/0.50 | +354.3% | +287.3% | **81%** | 48.7% |
| 3 | nn/rank/0.50 | +117.4% | +36.9% | 31% | 25.0% |

Trade-level dig (retrained + reproduced exactly, matched official numbers to
4 decimals) on all three folds' top trades: no repeat symbols within any
fold's top 5–8, no leveraged ETFs, max single-trade return +754% (fold 1) vs.
v3.1's uncorrected walk-forward where fold 2's +1136% was ~98% one 31x
overnight TQQQ trade (ex-top3 collapsed to +18%, 1.6% retained). v4's
worst-case retention (fold 3, 31%) is still far more broadly-based than
v3.1 ever showed. **This stage distinguished pipeline success from strategy
validity as intended: not a bug, and not just leakage — a real, smaller,
more broadly-distributed edge.**

### 1. Causal feature and split contract

Implement shared utilities for:

- Feature availability assertions.
- Exit-time purging and embargoes.
- Fold-local scaling and feature selection.
- Nested temporal model/threshold selection.
- Regression tests that construct deliberately leaking rows and fail if they cross a split.

Current implementation:

- [x] `nn_meta/feature_contract.py` records feature availability; the v4
  schema (`V4_META_FEATURES`) deliberately excludes `prem_spot` while the
  legacy schema remains intact for existing v3/v31 artifacts.
- [x] `nn_meta/temporal_validation.py` assigns splits using both `entry_ts`
  and `exit_ts`, purges cross-boundary labels, applies an explicit embargo,
  and records a split audit table.
- [x] `nn_meta/v4_evaluate.py` makes architecture/model-family, evaluation
  mode, and threshold selections inside each temporal fold. It can run both a
  corrected expanding-fold evaluation and a four-way legacy/v4 × unpurged/purged
  ablation against a completed v31 dataset.
- [x] Regression tests cover the feature-time contract, cross-boundary
  labels, embargo behavior, fold ordering, and shared policy selection.
- [ ] Refit the selected fold-local model on train+validation before its OOS
  test, if we choose that convention; the current conservative runner keeps
  validation separate through testing.
- [x] `nn_meta/v4_finalize.py` (Option A, 2026-07-21 night): the 3-fold
  walk-forward's nested selection means each fold independently picks its
  own winning family/mode/threshold (see stage 0 results — folds 1/2/3
  didn't agree), so there's no single "the config" to just retrain. This
  script runs one more nested-selection pass on the full dataset (all data
  as train, a validation tail for early-stopping/threshold choice, no
  held-out test — this pass exists to pick+train the deployable config, not
  measure OOS performance) and persists a `config.SEEDS`-size ensemble of
  the winner to `model_final_v4/`. Still uses the stage-2-pending shared
  portfolio simulator, not the mark-to-market ledger — see Option B below.

### 2. Execution and accounting

Define one evaluation contract for:

- Signal timestamp.
- Option contract selection timestamp.
- Entry fill timestamp and price.
- Exit signal timestamp.
- Exit fill timestamp and price.
- Roll behavior.
- Missing bars and fill failures.
- Mark-to-market option valuation.
- Conservative cost and spread scenarios.

Current implementation:

- [x] `nn_meta/v4_accounting.py` defines a fail-closed execution schema,
  explicit per-side cost scenarios, and an event-level cash/position ledger.
  True V4 reports require observed entry and exit contract marks and use any
  observed interim marks; the ledger never manufactures a mark from a final
  trade return.
- [x] The execution engine now retains gross return plus actual entry/exit fill
  timestamps, and future meta-datasets retain those execution-provenance
  fields.
- [x] The mark-stream format, deterministic keying, IO, and the ledger
  bridge live in `nn_meta/mark_stream.py`; the v4 evaluator routes the
  winning policy's entered trades through the ledger when a stream is
  supplied. Emission of a real per-contract 15-minute stream (including roll
  fills) from the label builder is still pending v31 data.
- [x] Fill-failure reason codes and conservative behavior for missing option
  bars/spreads are specified in `nn_meta/v4_accounting.py` (`FillFailure`,
  `FillPolicy`, `classify_quote`, `resolve_fills`). Wiring the real mark/label
  builder to emit them waits on v31 raw bars.

**Option B plan (scoped 2026-07-21 night; corrected 2026-07-22 after the
merge)** — the original premise ("`v4_accounting.py` is not imported by
either") was written before the MacBook's queue work landed: `v4_evaluate.py`
does import the ledger (`mark_to_market_portfolio`, `BASE_COSTS`) and
`marked_metrics()` routes the winning policy's entered trades through it when
`--marks` is supplied (queue item 1). The narrower statement that IS true:
fold/policy **selection** (`choose_policy` → `select_meta._portfolio_sim`)
still uses the old shared simulator, the ledger result is only a
supplementary "marked" metric on the winner, and every stage-0 result and
`model_final_v4` above was selected under the same shared simulator v3.1
used (the one a single TQQQ trade could dominate — stage 0's trade-level
digs suggest v4's config isn't fragile to that in the same way, but it
hasn't been re-checked through the stricter ledger). `v4_finalize.py`
genuinely does not touch the ledger. Constraint discovered 2026-07-22: the
committed v31 `meta_dataset.parquet` predates the execution-provenance
fields (no `entry_fill_ts`/`exit_fill_ts`/`gross_return` columns and no
per-contract mark stream), so a selection-side ledger can book only
`entry_ts`/`exit_ts` endpoint fills from `entry_premium`/`net_return` until
the dataset is rebuilt — decide explicitly how that squares with the
"never manufacture a mark" rule before wiring. Sequencing:

1. Wire `v4_accounting.py`'s event-level ledger into `evaluate_window()`
   (`nn_meta/v4_evaluate.py`) in place of `select_meta.portfolio_metrics`/
   `_portfolio_sim`, so fold/policy selection itself uses mark-to-market
   accounting, not just the final reported number.
2. Re-run the ablation (`--ablation`) and nested walk-forward (`--folds 3`)
   through the new ledger. Numbers are expected to move — that's the point;
   compare against the stage-0 table above rather than assuming it repeats.
3. Only after that: re-run `v4_finalize.py` for a new `model_final_v4/`,
   since Option A's persisted ensemble was selected and trained under the
   old simulator.
4. Then, and only then, stage 5 live parity **runs**: the candidate-batch
   constructor itself already exists (queue item 8,
   `nn_meta/live/v4_candidates.py`) — what waits is re-validating candidate
   parity against whichever model survives the ledger re-runs, not building
   the constructor.

### 3. Baseline bake-off

Evaluate GBT, NN, mechanical baseline, and underlying basket using identical portfolio construction. Prefer the simplest model that survives the same corrected out-of-fold gates.

Current implementation:

- [x] The v4 runner evaluates NN and LightGBM through the existing shared
  slot-portfolio evaluator, with the same frozen baseline, policy candidates,
  threshold set, and drawdown gate. A candidate must exceed its validation
  baseline to be eligible.
- [ ] Replace/extend that shared evaluator with the stage-2 mark-to-market,
  cost, and capacity accounting contract before treating outputs as live-ready.

### 4. Reproducible artifacts

Add:

- Locked dependencies and CI.
- Artifact manifests and fail-closed cache validation.
- Portable launchers and preflight checks.
- Coverage and entitlement reports.
- A small metadata bundle that can be transferred independently of multi-gigabyte raw data.

Current implementation:

- [x] `nn_meta/v4_artifacts.py` creates and validates fail-closed manifests
  containing file hashes, code revision, config hash, coverage, feature
  provenance, and provider metadata. The v4 evaluator writes one beside each
  report and can create a small transfer-ready metadata ZIP.
- [x] The manifest regression tests prove that changed dataset/spec inputs and
  changed ordered feature schemas are rejected.
- [x] A reproducibility snapshot lockfile (`requirements.lock.txt`) and a CI
  matrix (`.github/workflows/ci.yml`, ubuntu + macOS / Python 3.12) are in
  place; `requirements.txt` gained an explicit `scipy` pin target. A single
  fully-resolved cross-platform lockfile remains a future refinement.
- [x] `python -m nn_meta.v4_preflight --require-gbt` is a remote-safe
  preflight command for the actual v31 runtime. It validates local files,
  causal schema, baseline spec, and LightGBM availability before the ablation.
  Provider entitlement and cache coverage remain run-specific operational
  checks because this machine cannot inspect the separate remote environment.

### 5. Live parity

Make the deployed scanner consume the same candidate batch and policy as the backtest:

- Same strategy and DTE competition.
- Same available-at feature construction.
- Fresh data/cache controls.
- Atomic alert state and acknowledged notification outbox.
- Paper-trade ledger and drift/health metrics.

Current implementation:

- [x] `nn_meta.live.v4_parity.assert_feature_parity` makes the feature gate
  executable: it rejects post-decision fields, missing columns, row-count
  differences, and numerical mismatches (while handling matching NaNs).
- [x] The v4 live candidate-batch constructor is `nn_meta/live/v4_candidates.py`
  (`build_candidate_batch` + `assert_candidate_parity`), reusing the offline
  featurization so it is parity-correct by construction and needs no option
  fill. The deployed scorer intentionally remains the legacy v3/v31 scorer and
  still depends on `prem_spot`; it is not relabeled as v4 parity. Running it
  against the live provider's archived bars is the on-server step.
- [x] Atomic alert/outbox state, paper-trade ledger, and drift/health metrics
  are in `nn_meta/live/state.py`. Wiring them into the deployed scanner loop is
  the on-server step.

### 6. FA-to-universe loop

After the corrected trading evaluation is stable:

- Preserve raw social/news/filing snapshots.
- Complete entity resolution and alias fixtures.
- Add source-normalized attention velocity and corroboration rules.
- Freeze monthly rankings.
- Track forward returns.
- Graduate names into future universes only using their historical ranking date.

Current implementation:

- [x] `fa/universe_loop.py` ranks only score rows observed by the ranking
  timestamp, requires independent-source corroboration, freezes a dated JSON
  ranking without overwrite, and allows graduation only after a point-in-time
  probation/forward-return check.
- [x] The raw-collector → entity-resolution → normalized-score-table bridge
  is built (`fa/entities.py`, `fa/scores.py`), feeding
  `universe_loop.monthly_rank`. Accumulating enough dated rankings to evaluate
  the discovery signal is the forward-time step; historic social/filing
  snapshots cannot be reconstructed retroactively.

## Model-track roadmap — the four NN approaches at industry standard

The reference taxonomy (1. time-series forecasting, 2. market classification,
3. reinforcement learning, 4. hybrid/ensemble) describes tutorial-level
architectures. Industry standard is not a particular network; it is a strong
classical baseline plus the evaluation contract in stages 0–5: point-in-time
features, purged/embargoed nested selection, costed portfolio-level
out-of-fold results, calibration, multiple-testing control, reproducible
artifacts, and live parity. A track is "industry standard" here when its
neural model beats its boring baseline through that contract; it "exceeds"
standard when it also survives regime slices and the deflated-Sharpe /
seed-variance checks below. This section maps each track onto the project and
sequences the work that must land before the V4 training run.

### Track 2 — Market classification (closest to done; V4's core)

- Have: the meta-labeling MLP ensemble (P(win) on strategy-proposed options
  trades, |return|-weighted BCE, 40 seeds) already is the classification
  track, and the stage-1 purged/nested contract puts it ahead of the
  tutorial version of this idea. LightGBM bake-off is wired into
  `nn_meta/v4_evaluate.py`.
- Gaps (pre-queue state; both closed by queue items 3–4): probabilities
  were used for thresholding but never calibrated, and there was no
  multiple-testing control across policy/threshold candidates. Remaining
  real gap: PBO report wiring needs the per-fold candidate matrix.
- Plan:
  - [x] Fold-local probability calibration (isotonic or Platt fit on the
    validation slice only); Brier score and reliability reported beside the
    portfolio metrics. Implemented in `nn_meta/calibration.py` and wired into
    `v4_evaluate`.
  - [x] Deflated Sharpe ratio / probability-of-backtest-overfitting (PBO)
    across the policy grid. `nn_meta/multiple_testing.py`; deflated Sharpe is
    reported per winner. PBO utility is tested; report wiring for PBO needs
    the per-fold candidate matrix (follow-up).
  - [ ] Skip CNN-on-chart-images deliberately: it discards exact numerical
    information for pixels and is not used seriously in industry. Record
    this as a considered-and-rejected decision.
- Gate: calibrated OOS probabilities; NN beats the corrected LightGBM
  baseline and mechanical baseline at portfolio level, per regime slice.

### Track 1 — Time-series forecasting (regression, as volatility not price)

- Have: only the legacy v1 LSTM in `models/nn_model.py` (pre-contract, not
  usable as evidence) and 9y of 1-minute underlying history in `v3/data/`.
- Position: point-price regression is a known dead end (near-random-walk
  target, R² ≈ 0). The industry-standard regression target is volatility
  and expected-return distribution, which this project can actually use:
  vol forecasts price options, ranks DTE/strike candidates, and sizes
  positions.
- Plan:
  - [x] Classical baselines first: realized-vol HAR-RV and GARCH(1,1)
    forecasters with OOS QLIKE/pinball loss under the stage-1 folds, in
    `nn_meta/vol_forecast.py`. Runs on the local daily cache; the full 9y
    intraday-RV run happens where `v3/data/` lives.
  - [ ] One sequence model (GRU or temporal-conv; small) forecasting
    realized vol and return quantiles over option-holding horizons; it must
    beat HAR-RV/GARCH OOS per regime slice or it is dropped.
  - [ ] Feed the winning forecaster's outputs into the meta-feature schema
    as `available_at`-stamped features (forecast made strictly before the
    decision bar) — the forecasting track's product is features, not trades.
- Gate: sequence forecaster beats HAR-RV and GARCH on OOS QLIKE across
  regimes, and its features improve the track-2 model out-of-fold; otherwise
  the classical forecaster's features ship instead.

### Track 3 — Reinforcement learning (sizing/exit policy, not signal)

- Have: nothing. Honest framing: end-to-end RL trade generation is mostly
  not industry practice — sample-inefficient, seed-unstable, and prone to
  learning the simulator. What is industry practice is RL/bandit methods
  for execution, sizing, and exit policy on top of a validated supervised
  signal.
- Plan (strictly after stage 2's mark-to-market ledger exists, because the
  environment's reward is that ledger):
  - [ ] Offline first: treat threshold/size/exit-timing as a contextual
    bandit / fitted-Q problem over the historical per-contract 15-minute
    mark stream. No simulator interaction, so it inherits the purged folds
    directly.
  - [ ] Then a Gymnasium environment wrapping the stage-2 accounting
    contract (costs, fill-failure codes, mark-to-market), with
    stable-baselines3 PPO as the online learner. Train only inside temporal
    training folds; evaluate through the identical costed portfolio
    simulator as every other track.
  - [ ] Multi-seed (≥5) with seed-variance reported; an RL policy whose
    seeds disagree on sign is rejected regardless of mean.
- Gate: the learned policy beats the tuned supervised policy (track 2 +
  grid-selected thresholds) under identical costs and folds. If it only
  matches it, ship the simpler policy and record the result.

### Track 4 — Hybrid and ensemble (the V4 training run itself)

- Have: 40-seed deep ensembles; NN-vs-GBT bake-off; FA Stage-0 collectors
  archiving raw social/news/filing snapshots with collection timestamps;
  a lexicon-level `sentiment/` module not wired into training.
- Plan:
  - [ ] Sentiment features: transformer-based (FinBERT-class) scoring of
    the archived FA snapshots, `available_at` = collection timestamp,
    source-normalized. Only forward-accumulating — history that wasn't
    collected cannot be backfilled (same rule as stage 6).
  - [ ] Volatility features from track 1 (GARCH/HAR-RV at minimum).
  - [ ] Stacked blend: out-of-fold predictions from GBT, NN, and (if it
    survived) the sequence model combined by a simple fold-local blender
    (logistic or shallow GBT). Blend weights are selected inside folds like
    any other hyperparameter.
  - [ ] Component ablation table: every member must improve the blend
    out-of-fold or it is removed. The blend must beat the best single
    model, or V4 ships the single model.
- Gate: this is the model that the V4 training run promotes; it passes the
  first implementation gate below plus the track-2 calibration and
  deflated-Sharpe checks.

### Magnitude-aware labels / score-scaled sizing (carried-over backlog item)

Requested during v3.1; was reported as "logged in the project backlog" but
never actually written down — recorded here 2026-07-21. Evidence from the
v3.1 calibration analysis: win rate rises cleanly with model score, but
mean return inverts at the top of the score range — the model predicts win
probability, not win size. Its most confident trades win often but win
small, so ranking trades by score alone leaves magnitude on the table.

Candidate fixes, selected inside temporal folds like every other design
choice (they are not mutually exclusive):

- [x] Magnitude-aware labels: the return-bucket labels and magnitude
  regression target live in `nn_meta/ev_sizing.py`
  (`return_bucket_labels`, `magnitude_target`, `bucket_expected_value`).
  Training a head on them is the v31-data step; the labels are code-ready.
- [x] Score-scaled sizing: `nn_meta/ev_sizing.py` sizes positions by
  predicted EV (`predicted_ev`, `evaluate_ev`) instead of uniform slots,
  as a fold-selectable candidate. Empirical comparison vs uniform slots is
  pending the trained magnitude prediction on v31 data.
- [x] The v3.1 calibration table (score deciles vs win rate AND mean return)
  is a standard diagnostic in every v4 report via `nn_meta/diagnostics.py`,
  with an explicit top-decile-inversion flag, so the inversion is tracked
  continuously rather than rediscovered.
- Gate: mean return no longer inverts in the top score deciles
  out-of-fold, and EV-based sizing beats uniform-slot sizing through the
  same costed portfolio simulator; otherwise ship uniform slots and keep
  the diagnostic.

### Sequencing before the V4 training run

Dependencies, not dates. Each phase gates the next.

1. **Reconciliation + accounting (stages 0 and 2).** The v31 ablation ran
   (stage 0 DONE) and the reporting-side ledger routing exists; what
   remains is mark-stream emission from the label builder and the
   selection-side ledger swap (Option B steps 1–3). Everything downstream
   scores against this ledger.
2. **Baselines.** Corrected LightGBM (track 2) and HAR-RV/GARCH (track 1).
   No new neural work starts before its baseline exists — standing rule.
3. **Track 2 hardening.** Calibration + deflated Sharpe/PBO on the
   existing meta-model, plus the magnitude-aware label / score-scaled
   sizing experiments (see the carried-over backlog item above). This is
   cheap and upgrades every later comparison.
4. **Track 1 sequence forecaster** on the 9y underlying (compute-heavy;
   Windows/WSL2 box). Product: features for track 4.
5. **Track 4 features + blend** (sentiment scoring of the FA archive can
   start any time and runs in parallel; it only accumulates forward).
6. **Track 3 RL sizing** — last, because it consumes the stage-2 ledger,
   the track-2 supervised policy as its baseline, and the most compute.
7. **V4 training run**: the track-4 blend through the full stage 0–5
   contract, then live parity (stage 5) before any deployment.

Tracks 1 and 3 are additive, not blocking: V4 can pass its validation gate
on tracks 2+4 alone, with 1 and 3 promoted in a V4.1 once they beat their
baselines. The magnitude-aware label / score-scaled sizing work is NOT
optional in the same way: the v3.1 top-decile inversion means score-ranked
uniform slots are provably leaving return behind, so it belongs in the
track-2 hardening phase (step 3) alongside calibration.

## First implementation gate

V4 is not considered validated until:

- [x] `prem_spot` is removed or replaced with a truly pre-decision value.
- [x] Exit-time purging and embargoes are tested.
- [x] Walk-forward selection is nested.
- [x] GBT and NN are compared with the same costed portfolio simulator.
  (Same shared simulator as v3.1 — Option B above upgrades this to the
  mark-to-market ledger; that's a strengthening, not a redo of this item.)
- [ ] The live scorer passes an offline/online feature-parity test.

4/5 as of 2026-07-21 night. The remaining gate item is the reason
`model_final_v4/` (Option A) is a validated *candidate*, not a live
deployment — do not swap the scanner over to it until stage 5 closes this
out and Option B has been through at least one re-finalize pass.

## First remote v31 run — DONE 2026-07-21 night (results in stage 0 above)

All four commands below were run on the Windows/WSL box in sequence
(smoke test on a 10-symbol/~1y subset first, per `V4_SMOKE_TEST.md`, then
the real thing against the full 118-symbol dataset). Total wall time for
the ablation + nested walk-forward: ~17 minutes. `v4_finalize.py` (Option A,
not part of the original plan when this section was first written) then
trained + persisted `model_final_v4/` in another ~4.5 minutes.

```bash
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation --smoke
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_preflight --require-gbt
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate \
  --folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_finalize \
  --select-seeds 0,1,2,3,4 \
  --epochs 60 --gbt-estimators 600 --embargo 1D
# (--final-seeds omitted -> defaults to config.SEEDS, the same 40 seeds;
#  the "0,1,...,39" shorthand originally recorded here isn't parseable)
```

The ablation writes `v4_ablation_report.md` and JSON beside the configured
reports directory; the expanding-fold run writes `v4_walkforward_report.md`
and JSON. The four ablation treatments distinguish schema leakage
(`prem_spot`) from split leakage (entry-only assignment) without re-downloading
raw options data. LightGBM must be installed in the remote environment for
the GBT comparison; the local tests intentionally do not require it — it was
missing on the Windows/WSL box and had to be installed before the real run.

## Branch strategy

This outline lives on `codex/v4-causal-validation`. Keep `main` as the v3/v31 operational line until v4 passes the gates. Do not copy the entire project into a second repository; refactor shared providers and execution contracts incrementally.
