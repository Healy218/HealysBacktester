# Handoff — October 7, 2026 — ETFE leak fixed; v4 (no stop) hinges on ITM-expiry policy

## Focus and result

- **Dataset v1 / experiment v2 trained (84 fits), then invalidated:** the GBT
  learned the signal-bar VWAP fill (top-decile entries 4.9% below that minute's
  close). User selected next-minute VWAP fills
  ([amendment](docs/specs/ETFE_FILL_RULE_AMENDMENT_20261007.md)).
- **v3 (with stop, labels v2 / dataset v2 / experiment v3):** the models rank
  (AUC ~0.60) but no top decile is profitable; the all-eligible baseline loses
  85–91% per half-year.
- **v4 pre-registered** ([doc](docs/specs/ETFE_V4_PREREGISTRATION_20261007.md)):
  no premium stop, earliest exit, chosen from 2024-only evidence. Labels v3
  (no stop) audited; dataset v3 (742d2cf6…) and experiment v4 (e0b404c4…)
  frozen; 84 fits in `etfe-training-v4-20261007-r0`.
- **v4 validation replay** (`scripts/evaluate_etfe.py`, approximation): best
  configurations are positive in all three folds (up to +10% per half-year,
  drawdown under 10%), but each has 50–100 **blocked** selections
  (funding-unresolved ITM expiries). Treated as total losses, everything turns
  negative. See [EXPERIMENTS](docs/EXPERIMENTS.md).
- Training runs under `systemd-run --user --scope -p MemoryMax=20G` with per-fold
  streaming (a whole-dataset load crashed the session on Oct 7).

## Status at session end (Oct 7, evening)

The ITM-expiry amendment was selected (close at intrinsic value;
[amendment](docs/specs/ETFE_ITM_EXPIRY_AMENDMENT_20261007.md)) and its chain
launched: labels v4 (no stop + intrinsic) audited and passing (2,670,507
settled); dataset v4 frozen (`etfe-dataset-v4-20261007-r0`, e777af58…);
experiment v5 frozen (`docs/specs/ETFE_EXPERIMENT_V5_20261007.json`,
c64c828b…). Training v5 was at **52/84 fits** when the session ended. It may
have been stopped. Resume (completed receipts are skipped):

    systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0 ./venv/bin/python scripts/train_etfe.py \
      --root nn_meta/validation/etfe-training-v5-20261007-r0 --experiment docs/specs/ETFE_EXPERIMENT_V5_20261007.json

Then run `scripts/evaluate_etfe.py` with the same root and experiment
(validation replay, reference only). The 2026 test is the arbiter for v5.

The user decided to leave the 92 swept-in EXPERIMENTS lines in commit 8715581's
history; do not rewrite `main`.

## Next actions

1. **User decision:** ITM-expiry resolution for positions that cannot be sold
   (1% cap) or funded (isolated account). Candidates: close at intrinsic value
   (official close − strike, minus costs), broker-style exercise/liquidation, or
   keep unresolved (v4 fails). The kernel computes per-path intrinsic from
   `references`; relabel, then re-replay validation. This must be a declared
   amendment, applied before the 2026 test.
2. If a configuration then passes on validation: run the exact shared ledger to
   confirm, then the single 2026 test evaluation with stresses and bootstrap.
3. Commit hygiene: never use a path-limited `git commit -- file` on files with
   others' uncommitted hunks (8715581 swept in 92 EXPERIMENTS lines, undone in
   59d357d; they remain in that commit's history).

## Selected artifacts

[CURRENT_STATE](docs/CURRENT_STATE.md); labels v3, dataset v3, experiment v4 and
training v4 roots under `nn_meta/validation/`. Preserve unrelated dirty V6/V7 work.

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-v4-evaluation.md).
