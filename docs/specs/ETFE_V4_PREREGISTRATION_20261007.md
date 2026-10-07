# ETFE v4 pre-registration — October 7, 2026

Committed before any v4 label is computed outside the 2024 design period.

## Design (user-selected)

- **Exit:** earliest firing-variant exit (unchanged); **no premium stop**
  (`label_kernel` `stop_fraction=None`). Expiry-day logic is unchanged: 15:45
  cutoff, ITM sale, OTM roll into a later expiry, OCC exercise at the
  closing-auction reference, liquidation and settlement.
- **Fills:** next-minute VWAP ([amendment](ETFE_FILL_RULE_AMENDMENT_20261007.md)).
- **Scope:** SPY/QQQ, 1/5/15-minute signals, targets 0/1/5 plus 2/4 (unchanged).
- **Features:** v1 (unchanged). **Folds, 84 fits, hyperparameters, thresholds,
  selection and acceptance:** as in experiment v3.

## Evidence used for the choice (2024 design period only)

Pooled settled R under earliest exit: SPY-1 −7.61% with the 12.5% stop vs
+1.05% without; QQQ-1 −7.39% vs +1.76%. 5- and 15-minute signals were
−1.4% to −3.9% with the stop and −2.1% to −6.0% without. Without the stop, 52% of
SPY-1 2024 paths reach the expiry cutoff, the median R is −1.2%, and the top 1% of
trades carry 256% of total P&L: a tail-driven design. Latest-variant exits and
hold-to-cutoff were worse (−6% to −15%). No 2025 or 2026 label was computed under
any of these rules.

## Holdout and disclosure

The verdict uses the declared 2026 test period. That period's labels and model
scores were viewed once, in the v3 diagnostics, under the stop design (no v3
model had a profitable top decile). v4 2026 labels have not been computed.
Selection uses validation folds only, and the declared evaluation decides. A
forward paper period after 2026-10-02 is the confirming test. The tail
concentration above is a known risk; label stresses must hold.
