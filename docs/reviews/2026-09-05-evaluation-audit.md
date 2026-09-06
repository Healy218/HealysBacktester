# Evaluation, accounting, and model audit — 2026-09-05

> Remediated in the review checkout. See [the repair report](2026-09-05-remediation.md) for current dispositions and validation. Findings below refer to the original audited commit.

Reviewed revision `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`. Read-only source review; only this report was added. Reproduction scripts used `/tmp` and the existing production virtualenv interpreter with this review checkout on `PYTHONPATH`; no provider calls, training jobs, or production writes. Root reports complete suite **517 passed, 6 skipped**. The independent synthetic checks below expose cases outside that suite. No claim that existing historical headline returns have been recomputed.

Severity: P1 materially compromises causal evaluation/accounting; P2 correctness, reproducibility, or diagnostics defect; P3 smaller reporting issue. The September 4 adoption of risk-adjusted return versus baseline ex-top3 is treated as intentional. Reusing v5/v6 date windows is not itself a finding.

## Confirmed findings

### E01 — P1: “Nested” v4 evaluation does not nest the frozen proposal strategy

**Locations:** `nn_meta/v4_evaluate.py:709`, `:730`, `:945`, `:978`; `nn_meta/artifacts/baseline_spec.json:4`; `nn_meta/temporal_validation.py:80`.

The command loads one prebuilt dataset and one global baseline spec, then moves the neural/GBT split boundaries for each expanding fold. It never refreezes strategy parameters/DTEs or rebuilds proposals from that fold's training data. The committed baseline's training window ends **2025-12-19**, while the first OOS period starts halfway through the 2024–2026 data window, before that date. Thus outcomes from early OOS periods helped choose the underlying strategies and their frozen DTEs before NN training starts. Purging NN labels cannot remove this upstream optimization leakage. `V4_OUTLINE.md:49` says DTE and portfolio policy are selected inside temporal training folds; the implementation only nests the meta-model/policy selection. Such results are at best conditional on a globally optimized proposal generator, not an end-to-end OOS strategy audit. The legacy `walkforward_meta` does explicitly refreeze, demonstrating the missing stage. Fix direction: fold-local freeze and proposal generation, or explicitly restrict/report OOS to dates after the frozen baseline training horizon.

### E02 — P1: Entry-bar close marks are silently discarded

**Locations:** `nn_meta/v4_accounting.py:265–285`; `nn_meta/mark_stream.py:95–97`; `options/execution.py:191`.

The mark builder deliberately emits the first bar's **close/open return**, which can be nonzero. The ledger processes that timestamp's marks before opening positions, sees no position, skips the first mark, and initializes value at the unmarked entry price. A position marked down 90% on its entry bar and back to flat on its next/exit bar reports **0% drawdown**, even at 100% allocation and zero costs. That is a direct risk-gate bypass. Existing accounting tests use zero entry marks, hiding the discrepancy. Handle entry-open and bar-close as distinct ordered events and apply every observed close mark.

Related chronology problem: these marks carry the raw bar timestamp while representing its close. At a timestamp with a new entry, the ledger incorporates existing positions' same-bar closes before sizing an entry at that bar's open. With start-stamped vendor bars, this uses up to 15 minutes of future mark information. Correct event timestamps are necessary in addition to preserving the first mark.

### E03 — P1: The cash ledger permits unfunded entries and leverage

**Location:** `nn_meta/v4_accounting.py:282–285` (configuration-only check at `:239`).

`max_concurrent * position_fraction <= 1` does not guarantee cash sufficiency when previously opened options appreciate. Each new notional is a fraction of current marked equity; cash is debited without checking availability. Repro: start with equity 1, open A for 0.5, let A double to value 1, then open B at 0.5 of equity 1.5. B costs 0.75 although only 0.5 cash exists. Cash becomes **-0.25** and the emitted peak gross exposure is **116.67%**, despite the accepted 2 × 50% configuration. No financing or margin cost is booked. Cap/reject new fills based on free cash and an explicitly defined gross-exposure budget.

### E04 — P1: Rolls lose all intermediate execution costs in Option B

**Locations:** `nn_meta/mark_stream.py:95–97`, `:277–284`; `nn_meta/v4_accounting.py:269–273`.

Gross marks multiply the return of every roll leg, but the bridge drops roll/fill counts and the ledger applies only one opening haircut and one final closing haircut for the whole trade. The executor applies those costs once **per leg** (`options/execution.py:266`). A two-leg flat-price trade with 1% per side should return `(0.99/1.01)^2 - 1 = -3.921184%`; the marked ledger reports **-1.980198%**. Turnover is understated as well. This affects both candidate metrics and baseline, by differing amounts when roll counts differ. Persist roll execution events and apply each fill cost in the marked ledger.

### E05 — P2: Mark sidecars are not reconciled with the execution outcome

**Location:** `nn_meta/v4_accounting.py:198–218`.

Validation checks timestamp bounds and endpoint existence, but never checks the terminal mark against the required execution `gross_return`. A dataset trade declaring **-100%** realized return with a terminal sidecar mark of **+1000%** passes validation and reports **+1000%** portfolio return. A stale/rebuilt sidecar with the same logical trade IDs can therefore silently change the approved result. The trade's `gross_return` is otherwise never used by the ledger. Require terminal-return reconciliation with numeric tolerance and link the exact sidecar to input metadata.

### E06 — P1: Daily options selection looks ahead to exit-data availability

**Location:** `nn_options_signal/backtest.py:72`.

Before ranking candidates, the simulator drops rows lacking future exit price/date. Those fields are also set missing for label-window validity failures, including distant/missing exit bars. Having no future exit observation is not evidence that an entry order could not fill. The code replaces the originally highest-scored, entry-fillable contract with another candidate using information unavailable at the decision close. Repro with two otherwise identical names: highest score has missing exit; lower score has a doubling exit. The simulator chooses the lower-scored winner and reports **+8.7183%**. Supplying a zero exit for the original best score changes the selected name and result to **-9.1017%**. Choose from decision-time data, resolve the actual entry, and conservatively account for an already-open position with a missing exit.

### E07 — P2: Daily options “purged” splits do not inspect label exits

**Locations:** `nn_options_signal/build_dataset.py:112–118`, `:171–179`.

The label builder permits a horizon window up to `(h+1)*4` calendar days because it shifts the contract's observed bars, not an exchange-session index. Splits are then assigned solely from decision date. The 10-calendar-day validation/test gap is shorter than an allowed h5 label window of 24 days. For example, March 27 validation decision, March 30 next entry, then sparse observed bars through April 10 is a valid h5 label that reads prices after test starts April 6. Neither training nor selection purges such rows. Compare each horizon's realized exit to its partition boundary; calendar gaps alone are insufficient with sparse contract bars.

### E08 — P2: The daily drawdown metric forgets initial capital

**Location:** `nn_options_signal/backtest.py:125–128`.

The equity curve's first observation is after the first trade's realized P&L. `cummax()` starts from that already-reduced equity instead of initial capital. A single losing first trade with **-9.1017%** total return reports **0% max drawdown**. More generally the first loss and part of the subsequent recovery are hidden, directly weakening validation drawdown guardrails. Seed the curve/peak with initial capital. The curve also stamps realized exit P&L on decision dates (`:116–120`), so its timestamps cannot be interpreted as actual account equity dates.

### E09 — P2: Legacy walk-forward training labels can cross the OOS boundary

**Location:** `nn_meta/walkforward_meta.py:169–176`.

Fold splits use `entry_date` only even though label generation covers both train and OOS. A training/validation trade opened before `train_end` but closing during OOS is retained as labeled training/early-stopping evidence. This conflicts with the module's “everything re-derives from fold-train only” description. Use the existing exit-aware purging helper here too. This is separate from v4's global-freeze issue; v4's own label purging is implemented.

### E10 — P2: Walk-forward resume silently reuses a different experiment

**Locations:** `nn_meta/walkforward_meta.py:160–163`, `:204–210`, `:275–280`.

Saved results are keyed only by fold number. Rerunning with a different `--folds` count, membership mode, winner, or input dataset reads old `foldN_result.json` without checking any of those inputs. Even when the result is removed, cached predictions are accepted solely by array length, allowing same-length reordered or changed candidates to get someone else's scores. The report can therefore claim a new robustness run while using previous windows/configuration. Include experiment/input hashes and row identities in every checkpoint and validate them before reuse.

### E11 — P2: Isotonic calibration depends on ordering of tied scores

**Location:** `nn_meta/calibration.py:91–97`.

PAV is fit on individual observations before grouping duplicate score values. Equal-score labels can be split across different PAV blocks; averaging afterward does not recover the correct weighted isotonic solution. Repro with scores `[.5,.5,.6]`: labels `[1,0,0]` yield predictions `[1/3,1/3]`, while swapping only the two equal-score observations to `[0,1,0]` yields `[.25,.5]`. The data are identical as score/label multisets. Tree predictions commonly tie, so calibration selection and reported Brier can change under harmless row ordering. Aggregate counts/positive labels per distinct score before weighted PAV.

### E12 — P2: Volatility feature availability is one minute early

**Location:** `nn_meta/vol_features.py:68–70`.

The output uses the final minute bar's start timestamp as `available_at`, although all features include that bar's close. A normal last 15:59 NY bar produces `available_at=20:59 UTC` in winter; its close is only known at 21:00 UTC. The synthetic two-bar check reproduced that early stamp. A consumer honoring the advertised availability field can therefore join the completed daily RV one minute before it exists. Add the bar duration/use actual session close and preserve the distinction for thin sessions.

### E13 — P2: Regime diagnostic bins read future OOS distributions

**Location:** `nn_meta/vol_features.py:101–102`.

The trailing RV input is shifted causally, but `pd.qcut(trail, 3)` calculates bin boundaries once over the full history before folds. Thus a historical day's calm/mid/stressed label depends on later volatility. This affects regime-specific QLIKE and the stated seat-gate diagnostic, not the fitted HAR/GARCH predictions themselves. Fit the tercile cutoffs on each fold's training data or use an expanding past-only distribution.

### E14 — P2: The artifact manifest does not identify the mark stream that determined eligibility

**Locations:** `nn_meta/v4_finalize.py:409–417`; `nn_meta/v4_evaluate.py:989–995`; `nn_meta/v4_artifacts.py:56–86`.

Dataset/spec/model files are hashed, but the Option B sidecar is only recorded as a pathname during finalization and is not even recorded by the evaluation manifest. Mark paths determine maxDD, returns, policy selection and eligibility independently of final dataset returns. Replacing intermediate marks at the same pathname leaves every recorded input hash unchanged, so these manifests cannot reproduce or validate the gate's decisive input. Hash the mark stream and persist execution/cost scenario plus effective gate configuration alongside it. Evaluation JSON/Markdown also omits the effective gate name (`risk` default), while Markdown still describes a raw ex-top3 return comparison.

### E15 — P2: Every candidate repeatedly validates and sorts the full mark universe

**Location:** `nn_meta/mark_stream.py:287–288`.

`load_mark_stream()` already validates/sorts the full sidecar. Nevertheless every `execution_frames()` call copies, validates, duplicate-checks, and sorts the **whole** stream before selecting the handful of relevant IDs. Each policy invokes it again for ex-top3; optional baseline redraws multiply it further. The module documents approximately 88 million marks, so this is a repeated full-universe allocation/sort inside the grid, not a selected-window operation. This can turn validation sweeps into memory/CPU failures. Filter the already-validated stream first or pass a validated/indexed object. This finding is based on the call path and complexity; no full 88-million-row benchmark was run.

## Additional concerns and smaller defects

- **P2, atomic deployment gap:** `v4_finalize.py:213–217` uses two separate renames: old final to `.prev`, then staging to final. A process kill or machine crash between them leaves no bundle at the advertised path; the exception rollback does not execute after a kill. The previous bytes survive under `.prev`, but readers fail until manual recovery. This contradicts the docstring's continuous availability claim. A pointer/symlink swap or recoverable startup protocol would address it.
- **P2, incomplete verification envelope:** `v4_loader.py:178–191` only validates entries listed in `output_artifacts`, without requiring the actual ensemble config and every member/scaler/magnitude file to be included. An incomplete manifest can report verification success while load-critical files remain unchecked. The normal finalizer emits a complete list, so this is a robustness/integrity concern for externally assembled or damaged manifests, not a claim of compromised current output. `load_final_v4()` itself does not verify; the live scanner does call `verify_bundle()` first.
- **P3, fold tail omitted:** `temporal_validation.py:81–85` floor-divides remaining days among folds and never adds the remainder to the final fold. With 20 days and three folds, the last day is not tested. Preserve the remainder in the final window.
- **P3, zero baseline treated as missing in legacy gates:** `select_meta.py:285` and `walkforward_meta.py:229` use `baseline_return or -inf`; a legitimate zero-return baseline is consequently passed by a negative-return strategy. Use an explicit `is None` test.
- **Observed limitation, not newly promoted as a defect:** EV braking is deliberately based on realized-close drawdown per `ev_sizing.py` and the August 26 decision. In marked runs those precomputed fractions are replayed rather than recalculated from interim marked drawdown. Reports should retain that distinction; I did not classify the documented realized-DD choice as an unintended bug.

## Reproduction evidence

Preserved self-contained script: [repros/evaluation_audit.py](repros/evaluation_audit.py). Executed its equivalent `/tmp/eval_audit_repros.py` during review; rerun the preserved version with:

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/healy/Coding/HealysBacktester/venv/bin/python docs/reviews/repros/evaluation_audit.py
```

Observed: ignored entry dip maxDD `0.0`; mismatched endpoint total return `10.0`; peak exposure `1.1666666666666667`; initial daily loss total return `-0.091017`, maxDD `0.0`; two-leg cost actual `-0.01980198019801982` versus correct `-0.03921184197627692`; future-exit availability switches chosen ticker and return `+0.087183` versus `-0.091017`; final-minute feature availability `2025-01-02 20:59:00`. Separate direct isotonic calls produced the tie-order discrepancy quoted above. Static findings explicitly identify the trigger and exact implementation path; no production artifact performance attribution is inferred from synthetic returns.

## Coverage and limits

Source read: `nn_meta/v4_evaluate.py`, `v4_finalize.py`, `v4_loader.py`, `v4_accounting.py`, `v4_artifacts.py`, `v4_preflight.py`, `mark_stream.py`, `temporal_validation.py`, `feature_contract.py`, `select_meta.py`, `walkforward_meta.py`, `ev_sizing.py`, `calibration.py`, `multiple_testing.py`, `diagnostics.py`, `vol_forecast.py`, `vol_features.py`, `model.py`, `train_meta.py`; all Python modules under `nn_options_signal` (config, data downloads, dataset construction, model, train, select/evaluate, backtest; package init is empty). Cross-references inspected in `options/execution.py`, `nn_meta/config.py`, and live verification call sites. The dataset/freeze/provider/SPX0 and live/student subsystems are assigned to the other reviewers.

Tests read in detail: `test_v4_accounting.py`, `test_v4_finalize.py`, `test_v4_loader.py`, `test_v4_artifacts.py`, `test_v4_preflight.py`, `test_temporal_validation.py`. Relevant test inventory and fixtures reviewed in `test_v4_evaluate.py`, `test_mark_stream.py`, `test_calibration.py`; the root ran the full suite once. No NN/GBT fitting or full-dataset evaluation was attempted.

Non-Markdown artifacts inspected: the committed baseline spec's provenance/window; all eleven JSON files under `nn_options_signal/model_final/short` (ensemble config plus five seed params/scalers). The five scalers have consistent feature names and no zero/NaN std entries. Binary model weights and unavailable large market caches were not numerically audited or retrained. No additional substantive non-Markdown documentation was present in this assigned subtree beyond those model metadata artifacts.
