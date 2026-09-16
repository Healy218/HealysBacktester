# V7 runnable model trial pilots

## Implemented

`nn_meta/v7/trials.py` and `scripts/run_v7_model_pilot.py` connect the verified
factorized fold selections and train-only preprocessing to actual constant,
LightGBM and TensorFlow fits. They do not launch a full campaign. Each split is
limited to 65,536 observations; full binned-memory and integrated readiness
remain required before increasing that limit through a separate reviewed runner.

The declaration `docs/specs/V7_MODEL_TRIALS_20260916.json` contains **21 initial
model trials**: three objectives, each with one constant baseline and three seeds
(11/29/47) for each of GBT and NN. Initial objectives are ordinary win,
absolute-return-weighted win and winsorized-return Huber. The constant baseline
uses the weighted training-target mean; it is not claimed to be the optimal
Huber intercept. All models use identical purged row selections. GBT keeps raw
NaNs for missing-value branches; NN uses the train-only missing-value imputation
and standardization already implemented.

GBT parameters are 200 rounds, 31 leaves, learning rate .05, minimum leaf count
20, 63 bins and Huber alpha .9. The NN is 64/32 ReLU units, Adam .001, ten
fixed epochs, Huber delta 1 when applicable. These Huber implementations have
different robustness parameters. Comparisons report unweighted validation
log-loss/Brier scores or raw-return MAE/RMSE, not training-loss equivalence.
Both have one inner thread. Data order is explicitly fixed; no validation-based
early stopping or budget tuning occurs. All objectives and seeds remain in the
record; no winner or threshold is selected by this component.

Calibration is explicitly **none** for these initial comparisons. Weighted-win
outputs are not assumed calibrated win probabilities. Any later calibration,
threshold/ensemble search or portfolio selection needs its own declaration and
training-only/nested chronological evidence. The 21-trial inventory is not a
multiple-testing correction or completed PBO calculation.

## Provenance and failure behavior

Before fitting, the runner writes its declaration, source/runtime/input binding
and start timestamp into a unique partial directory. Failed attempts stay there
without a completion receipt. Completed reuse requires the same declaration,
code/runtime and inputs, then rechecks transitive source-shard payloads. Source
or payload mutations during fitting prevent sealing. A changed plan cannot
reuse an old completed output. Predictions are retained in exact validation
selection order, bound to the fold receipt; original raw labels remain there.

Pilot source binding covers loaded project dependencies, every V7 Python source,
the CLI and requirements without recursively walking historical data directories.
Any newly imported project module during fitting invalidates that binding.
This is explicitly a **component** binding; full-campaign `RunBinding` and
readiness checks are unchanged. The first test attempt using full recursive
source traversal was interrupted after 151.56 seconds before any test completed.
It was not a model failure and no V6 process was stopped.

Both model families save and reload their actual model, then verify every
validation prediction against the original. Nonfinite targets, weights, losses,
NN parameters, predictions or metrics fail. Classifiers require both training
classes to have positive weight. Output disk reserve is checked before and
after fitting; CLI uses the repository artifact disk with a 100 GiB reserve.

GBT consumes the bounded Sequence and records construction time and process
peak RSS after binning. This RSS is the process high-water mark, not an isolated
binned allocation or proof of full-history resource feasibility. No four-worker,
no-swap or V6-coexistence performance claim is made.

## Verification

Focused tests: **15 passed** in 6.00 seconds across trials, preprocessing and
folds (`/tmp/v7-trials-20260916-focused-final.log`). Actual TensorFlow and
LightGBM exercise all three objectives. Synthetic tests verify exact repeated
seed predictions, model reload parity, changed validation labels leaving fits
and preprocessing identical, stale-plan rejection, wrong-fold rejection,
changed source payloads, mutation during fit, failed partial receipts, row/disk
limits and validation-only missing features. They are software evidence, not
historical trading performance. Full-suite result is recorded in HANDOFF.

The old `v7-factorized-pilot-20260915` store remains historical: v1 schema,
March 7-era observations and floating-point label clocks. It was inspected and
was **not** relabeled, converted or trained as an eligible V7 fold.

Usage after preparing a suitable bounded current-contract fold:

```bash
./venv/bin/python scripts/run_v7_model_pilot.py \
  --fold nn_meta/validation/NEW/selection \
  --preprocessing nn_meta/validation/NEW/preprocessing \
  --trial gbt-win-11 --output nn_meta/validation/NEW/gbt-win-11
```

Provider/library references checked for this implementation:
[LightGBM deterministic parameters](https://lightgbm.readthedocs.io/en/latest/Parameters.html)
and [Keras batch training and sample weights](https://keras.io/api/models/model_training_apis/).

Full-history assembly, executable campaign scheduling, calibration/selection
amendments, portfolio baselines and multiple-testing diagnostics remain open.
No full readiness stage is marked passed by these component tests.
