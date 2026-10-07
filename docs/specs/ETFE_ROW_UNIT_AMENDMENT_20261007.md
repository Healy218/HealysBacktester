# ETFE row unit and exit amendment — October 7, 2026

User-selected amendment to [ETFE_EVALUATION_20261003](ETFE_EVALUATION_20261003.md)
row identity and the execution contract's strategy-exit semantics, for the first
run.

## Why

Variant-level rows `(decision_ns, security, variant, right, target, contract)`
total **233,055,707** selected logical memberships. At 442 float32 features that
is about 412 GB, and LightGBM's binned matrix alone would need about 103 GB of
RAM, against a 30 GiB host and a 400 GB storage budget. Variant-specific features
and exits make most rows distinct, so multiplicity deduplication cannot help.

## Row unit

One row per **decision clock** `(decision_ns, security, timeframe, right, target,
contract)` from selection v2: 6,650,729 selected rows. Which variants fired at
that bar is represented by declared summary features (per-family firing counts
and the total), computed causally at signal close. Variant identity is not a row
key. Logical memberships remain in the census for reporting.

## Exit rule

Besides the 12.5% premium stop and the expiry-day cutoff (15:45 ET; 12:45 on early
closes), the position exits at the **earliest exit signal among the variants
that fired the entry** on the same timeframe and right: call exit = channel 1,
put exit = channel 3, the first exit bar strictly after the entry bar. Exit
execution uses the same next-completed-bar reference mechanics as entry. At the
cutoff no firing variant has exited yet, so the OTM roll rule applies while the
row's position remains open. Everything else in the execution contract is
unchanged.

The isolated label account, costs, participation, settlement, exercise and
right-censoring rules are unchanged. This amendment does not alter targets
(win, weighted win, robust return) or folds.
