# ETFE first build, freeze, train and expert acceptance

This specification defines completion evidence for the user-requested first
ETFE research run. [ROADMAP](../../ROADMAP.md#etfe-first-run-sequence) owns the
sequence/dependencies; [TODO](../../TODO.md) owns only the selected phase's tasks.
[ETFE scope](ETFE.md) and the [VWAP amendment](ETFE_VWAP_20261003.md) own trading
semantics. This document does not create a second execution queue or change the
existing frozen configuration.
The [October 3 declarations](ETFE_CONTRACT_20261003.md) now specify the four
component contracts and [exact experiment design](ETFE_EXPERIMENT_20261003.json).
They do not close the unresolved source gate or replace the later dataset freeze.
The [fresh-Alpaca successor](ETFE_FRESH_ACQUISITION_20261003.md) permits bounded
raw downloads while admission validation continues; provider-global history
proof and old project metadata repairs are not collection prerequisites.
The [October 4 DTE successor](ETFE_DTE_20261004.md) caps all purchases/rolls at
1–5 calendar DTE and removes target 7. Both override the earlier declarations
within their named scope, preserving the original frozen artifacts.

## Meaning of a working expert

A reproducible research artifact that loads from an immutable trained bundle,
constructs the declared causal features, emits its documented prediction scores
and eligibility/decision/abstention outputs, and reproduces held-out replay in a
clean process. It must have completed the full scoped dataset build, input and
dataset freezes, all required model fits, evaluation and trained-bundle freeze.
It need not be attached to a broker to satisfy this milestone. A working research
artifact is not automatically a profitable, accepted or deployed trading expert.

## Contracts required for admission; bounded raw acquisition may precede closure

| Contract | Required contents |
| --- | --- |
| Data/history | Earliest provider boundary evidence, per-series usable start and warmup, October 2, 2026 inclusive cutoff, calendar/session/DST conversions, contract identity/actions/deliverables and feed/source bindings |
| Coverage | Expected contract/session/event demand; documented no-trade versus transport/provider absence; complete pagination/retries, duplicate/correction handling, checksums and auditable exclusions |
| Feature mapping | Every inherited field classified as retained, causally recomputed, explicitly replaced or unresolved; formulas, inputs, time windows, available-at time, missingness and names/dtypes. No fabricated quotes or unannounced feature removal |
| VWAP execution | Completed-bar reference, lag/revision assumptions, 1s latency/60s entry window, sizing/participation limits, missing entry/held/exit reference behavior, costs, premium-stop denominator, rolls/expiry/stock delivery and full accounting |
| Evaluation | Explicit target formulas, label horizons and unresolved outcomes, fold dates, ten-session embargo/full-horizon purge, train-only preprocessing, trial/search ledger, metrics, thresholds/ties and acceptance criteria |
| Resources | Current measured free storage and reserve, peak working/temporary/freeze footprint, RAM per worker and host reserve, autosized worker/thread policy, request limits and bounded checkpoints |

The earliest provider timestamp is not established by one contract's first bar.
Final historical bars also do not prove original publication times. Record the
admitted research assumptions and stress tests explicitly; inability to meet a
required point-in-time contract must remain visible rather than being relabeled
as observed data. Quote-derived IV/Greeks or liquidity measures need audited
inputs and new semantics where applicable; a trade VWAP alone is not their proof.

Complete final outcomes must fit inside the fixed data window. Predeclare and
count warmup-ineligible proposals and end-boundary outcomes requiring later
exit/roll/stock settlement; censor or exclude as specified, never invent an exit
at October 2 or silently extend the data window. Eligibility exclusions must be
decided from contract rules, not retrospectively chosen to improve performance.

## Input and dataset freezes

An **input freeze** contains the full required source inventory, raw/normalized
partition hashes and provenance, coverage/missingness reports, dated identities,
calendars and the capture code/config/environment identity. Raw responses do not
become point-in-time admissible merely because they are frozen.

A **dataset/experiment freeze**, completed before full training, binds:

- The input freeze and approved execution/feature contracts.
- Every dataset partition, schema/dtype/order, row identity and label definition.
- Full counts by ticker, timeframe, family, contract/session and eligibility
  disposition; physical storage may factorize shared features without losing
  logical combinations or lineage.
- Proposal, entry, feature-availability and full exit/roll/settlement times.
- Exact fold membership and purging/embargo evidence, not random train/test splits.
- Training-only imputation/scaling/encoding rules; fitted state is subsequently
  saved per fit, never calculated from validation/test rows.
- Trial families/objectives/seeds/hyperparameters, model-selection and decision
  thresholds, baseline definitions, metrics and acceptance criteria predeclared
  before outcome inspection. No search on the final test segment.
- Source hashes, dependencies, commands, resources and restart/verification receipts.

The fixed catalog has 20 families, 2,817 parameter variants per timeframe and
25,353 ticker/variant combinations. These are not row counts or model-fit counts.
Directions, DTE choices, contracts, events, folds and trials add separate dimensions.
Source snapshots must preserve any shared dirty code actually used; do not include
unrelated work in the scoped implementation commit or hide it from artifact lineage.

## Initial finite training design

Carry forward the research comparison design in the
[V7 model-trial reference](V7_MODEL_TRIALS_20260916.json) into an independently
declared ETFE experiment, adapting schema and history rather than executing the
old manifest. The starting design is 21 configurations per fold: three constant
baselines, plus GBT and neural-network fits for each of three objectives (win,
weighted win and robust net return) at seeds 11, 29 and 47. Model input dimensions,
fold dates, target definitions, resource settings and hyperparameters must be
sealed for ETFE after the representative pilot, before full fitting.

Include each required fold and any predeclared final refit in the campaign census.
All declared fits must finish; partial checkpoints or a single successful fit do
not complete the run. No V7 weights, old feature-schema relabeling or reuse of
validation/test observations in preprocessing, threshold selection or calibration.
Weighted-win scores are not automatically calibrated win probabilities.

Record prediction metrics appropriate to each objective (including probability
calibration only where claimed), and net-return, drawdown, exposure, turnover,
trade/skip counts and uncertainty for the shared-capital decision policy. Compare
against constant/no-model strategy baselines and an abstain/cash reference under
the same eligible inputs, costs and ledger. Preserve per-ticker/timeframe/regime
results; SPY/VOO correlation prevents treating every row as independent evidence.
Predeclare stress comparisons for costs, delayed bars and sparse liquidity.

Choose model/threshold/refit policy from training/validation evidence only;
report final held-out results without retuning on them. Periods previously
inspected in predecessor research remain revalidation, not a newly untouched
market-history claim. If no candidate meets acceptance criteria, freeze a rejected
research result and keep the operational decision at abstain/no promotion.

## Trained bundle and completion evidence

The **trained-bundle freeze** binds model weights, per-fit preprocessing,
schema/feature order, selection and decision policy, all trial metrics/predictions,
fold memberships, seeds/configuration, input/dataset hashes and environment/source
versions. Preserve accepted and rejected outcomes with distinct status fields.

Before calling the first research run complete, verify:

1. Full acquisition/build/fits reconcile against declared coverage and trial censuses.
2. Independent hash/census checks pass for input, dataset and trained freezes.
3. A clean process loads the bundle and reproduces stored predictions within
   declared numerical tolerances on replay data not used to fit that model.
4. The expert produces documented scores plus eligibility/decision/abstention;
   mismatched schema, altered source/data and stale/invalid input fail visibly.
5. Interrupt/restart and restore from a separately located verified copy reproduce
   output and preserve accounting. Storage destination/free space is verified
   before copying; the V7 archive is not overwritten or used as scratch space.
6. A dated review and EXPERIMENTS entry report actual evaluated verdicts and their
   limits. ROADMAP closes only gates with linked evidence; CURRENT_STATE selects
   actual artifact paths and HANDOFF identifies the next user-selected milestone.

Technical completion, performance acceptance and deployment are separate fields.
Missing data or causality defects block completion; a valid negative performance
result completes the experiment but does not earn operational promotion.
Future paper/live deployment and continual retraining require their own scoped
milestones, freshness/forward-parity evidence and operating admission.
