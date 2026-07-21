# v4 Outline — Causal Validation and Research Reproducibility

Status: implementation in progress. Created from commit `5474335` on
2026-07-20; causal-validation infrastructure was added on
`codex/v4-causal-validation` the same day. Empirical results remain blocked
until the remote v31 dataset/artifacts are available.

**Fresh coding session? Start at "Coding-session work queue" below.** It
separates what is already built, what is blocked on the remote v31
artifacts, and what can be coded and tested locally right now.

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
2. [ ] **Stage 2 — fill-failure reason codes.** Enumerate reason codes and
   fail-closed behavior for missing option bars/spreads in
   `nn_meta/v4_accounting.py`; test every code path.
3. [ ] **Track 2 — fold-local probability calibration.** Isotonic or Platt
   fit on the validation slice only, inside `nn_meta/v4_evaluate.py`;
   Brier score + reliability table beside AUC in reports. Tests prove the
   calibrator never sees test rows.
4. [ ] **Track 2 — deflated Sharpe / PBO utilities.** New module
   (`nn_meta/multiple_testing.py`), pure functions with tests against
   known analytic cases; wire into the walk-forward report.
5. [ ] **Backlog — score-decile diagnostic.** Emit score deciles vs win
   rate AND mean return in every v4 report, so the v3.1 top-decile
   inversion is tracked continuously.
6. [ ] **Backlog — magnitude head / EV sizing (code only).** Second
   E[win size] head (or return-bucket labels) plus EV-based slot sizing
   as a fold-selectable policy candidate. Synthetic-data tests now;
   empirical evaluation when v31 data lands.
7. [ ] **Track 1 — HAR-RV/GARCH baseline module.** Realized-vol targets
   plus HAR-RV and GARCH(1,1) forecasters with OOS QLIKE/pinball
   evaluation under the stage-1 fold utilities. Code + fixture tests
   locally; smoke-run on the legacy local cache; full 9y run happens on
   the machine that holds `v3/data/`.
8. [ ] **Stage 5 — live candidate-batch constructor.** Build the v4 batch
   constructor, run it against archived closed bars, and verify with
   `nn_meta.live.v4_parity.assert_feature_parity`.
9. [ ] **Stage 5 — alert/outbox/paper-ledger state.** Atomic alert state,
   acknowledged notification outbox, paper-trade ledger, drift/health
   metrics.
10. [ ] **Stage 4 — lockfile + CI.** Pinned, platform-tested lockfile and
    a CI workflow running the test suite on macOS and Linux.
11. [ ] **Stage 6 — FA score-table feed.** Wire the existing raw
    collectors and entity-resolution fixtures into the normalized score
    table consumed by `fa/universe_loop.py`.

### Blocked until remote v31 artifacts arrive — do not attempt

- Stage 0 reconciliation runs, the "First remote v31 run" commands, and
  every empirical result or report.
- Real calibration / deflated-Sharpe numbers and the magnitude-head
  evaluation (their *code* is queue items 3–6; their *numbers* wait).

### Explicitly deferred — do not start

- Track 3 RL (requires the stage-2 ledger and a validated supervised
  policy as its baseline).
- Track 1 sequence forecaster (requires its classical baselines from
  queue item 7 to exist and be beaten).
- Track 4 sentiment scoring at scale (FA archive lives on the Hetzner
  server; only fixture-level plumbing belongs in a local session).

## Stages

### 0. V31 reconciliation

Use the completed remote v31 artifacts to run:

- Existing v31 configuration.
- Existing data with `prem_spot` removed.
- Existing data with exit-time purging.
- Existing data with both corrections.
- Corrected LightGBM baseline.
- Corrected NN ensemble.

This stage should distinguish pipeline success from strategy validity without requiring a fresh raw-data download.

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
- [ ] Specify fill-failure reason codes and conservative behavior for missing
  option bars/spreads before producing a live-readiness report.

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
- [ ] Add a pinned, platform-tested lockfile and CI matrix. `requirements.txt`
  is version-pinned for the most brittle core packages, but it is not yet a
  fully reproducible lockfile.
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
- [ ] Build the v4 live candidate-batch constructor, run it against archived
  closed bars, and use this comparator against the matching offline row.
  The current deployed scorer intentionally remains the legacy v3/v31 scorer
  and still depends on `prem_spot`; it must not be relabeled as v4 parity.
- [ ] Add atomic alert/outbox state, paper-trade ledger, and drift metrics.

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
- [ ] Feed the existing raw collectors and entity-resolution fixtures into
  the normalized score table, then begin accumulating enough dated rankings
  to evaluate the discovery signal. Historic social/filing snapshots cannot
  be reconstructed retroactively.

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
- Gaps: probabilities are used for thresholding but never calibrated;
  no explicit multiple-testing control across policy/threshold candidates.
- Plan:
  - [ ] Fold-local probability calibration (isotonic or Platt fit on the
    validation slice only); report Brier score and reliability beside AUC.
  - [ ] Deflated Sharpe ratio / probability-of-backtest-overfitting (PBO)
    across the policy grid, reported in `v4_walkforward_report.md`.
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
  - [ ] Classical baselines first, from the 9y underlying: realized-vol
    HAR-RV and GARCH(1,1) forecasters with OOS QLIKE/pinball loss under the
    same fold boundaries as the trade evaluation.
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

- [ ] Magnitude-aware labels: move beyond the binary win label — predict
  E[net return] directly (regression head), or classify into return
  buckets so the label itself carries size. The current |return|-weighted
  BCE weights the loss by magnitude but still trains a pure P(win) target.
- [ ] Score-scaled sizing: keep the P(win) head, add a second magnitude
  head, and size positions by predicted EV = P(win) × E[win size] instead
  of uniform slots.
- [ ] Make the v3.1 calibration table (score deciles vs win rate AND mean
  return) a standard diagnostic in every v4 report, so the top-decile
  inversion is tracked continuously rather than rediscovered.
- Gate: mean return no longer inverts in the top score deciles
  out-of-fold, and EV-based sizing beats uniform-slot sizing through the
  same costed portfolio simulator; otherwise ship uniform slots and keep
  the diagnostic.

### Sequencing before the V4 training run

Dependencies, not dates. Each phase gates the next.

1. **Reconciliation + accounting (stages 0 and 2).** Run the v31 ablation
   when remote artifacts land; finish the per-contract mark stream and
   route the evaluator through the ledger. Everything downstream scores
   against this ledger.
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

- `prem_spot` is removed or replaced with a truly pre-decision value.
- Exit-time purging and embargoes are tested.
- Walk-forward selection is nested.
- GBT and NN are compared with the same costed portfolio simulator.
- The live scorer passes an offline/online feature-parity test.

## First remote v31 run

Once v31 training has completed and its `meta_dataset.parquet` plus baseline
specification are copied or made accessible to this branch's environment, run
the following from the project root (start with the smoke run to confirm the
remote dependencies):

```bash
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation --smoke
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_preflight --require-gbt
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate \
  --folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
```

The ablation writes `v4_ablation_report.md` and JSON beside the configured
reports directory; the expanding-fold run writes `v4_walkforward_report.md`
and JSON. The four ablation treatments distinguish schema leakage
(`prem_spot`) from split leakage (entry-only assignment) without re-downloading
raw options data. LightGBM must be installed in the remote environment for
the GBT comparison; the local tests intentionally do not require it.

## Branch strategy

This outline lives on `codex/v4-causal-validation`. Keep `main` as the v3/v31 operational line until v4 passes the gates. Do not copy the entire project into a second repository; refactor shared providers and execution contracts incrementally.
