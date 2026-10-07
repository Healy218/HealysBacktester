# Handoff — October 7, 2026 — ETFE labels, stresses and features complete

## Focus and result

Since the envelope capture (see the previous handoff), with user decisions in
[DECISIONS](docs/DECISIONS.md):

- **Label kernel** (`nn_meta/etfe/label_kernel.py`): isolated-path labels for all
  6,650,729 decision-clock rows in ~2 min. Exact parity with the per-second
  `Scheduler` on all six fixture tapes; the independent audit reconciles every
  filled entry against raw bars. Baseline r2: 2,625,092 settled, 147
  input-unresolved. Rejected: r0 (cost rounding order), r1 (Jan 9, 2025 expiry,
  post-end censoring, liquidation completion).
- **Decisions:** keep 1% participation (49% size-ineligible); train SPY/QQQ only
  (VOO has 18 settled rows); OCC Jan 9 → Jan 8, 2025 expiry override.
- **Stresses:** all 27 profiles (r1; r0 rejected for strategy-off parity). Pooled
  settled R: baseline SPY +0.30% / QQQ +0.11%; cost ×3 about −0.3 to −0.5%;
  combined −3.8% / −7.0%. Unfiltered signals are roughly break-even, so any edge
  must come from model selection.
- **Features v1** (`nn_meta/etfe/feature_build.py`, [amendment](docs/specs/ETFE_FEATURE_AMENDMENT_20261007.md)):
  6,589,460 SPY/QQQ rows × 442 columns, 723 MB. Family firing fractions,
  aggregated signal fields, IV context from census daily bars, masked params and
  trade-only fields. The audit passes, including prefix causality. Peak RSS
  8.3–8.5 GiB per ticker process.
- 358 ETFE tests pass.

## Next actions

1. **Dataset assembly and freeze (ETFE-3.freeze):** join features and labels by
   key, record purge horizons (terminal settlement), sessions and row census, and
   seal partitions with hashes.
2. **Experiment successor (ETFE-4.admission):** the current declaration has the
   pre-amendment feature schema hash and a pending history start. A v2 needs the
   amended schema hash, history start 2024-01-18, SPY/QQQ scope and the
   decision-clock row identity. Keep 84 fits and the fixed hyperparameters.
3. **Training smoke (ETFE-4.pilot):** one fold × GBT/NN to measure fit peak RAM
   and time, plus interrupted-restart recovery; then size workers with
   `scripts/lib/autosize.sh` (each feature/label worker peaked at ~8.4 GiB).
4. Full training (84 fits), evaluation against baselines and stresses, freeze,
   and expert proof.

## Selected artifacts

[CURRENT_STATE](docs/CURRENT_STATE.md) rows: labels r2, label stress r1,
features v1, envelope, selection v2, existence census, dated policy, exercise
references. Never edit a capture-root-pinned file. Preserve unrelated dirty
V6/V7 work, including uncommitted DECISIONS hunks.

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-dataset-freeze.md).
