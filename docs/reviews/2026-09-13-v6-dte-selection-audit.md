# V6 DTE and extreme-return selection audit — September 13, 2026

Campaign: `v6-cash-repair-20260913`. This is a read-only model/selection audit;
no model, threshold, source policy or historical campaign artifact was changed.
The user requested exact rules explaining absent short-DTE selections and the
absence of greater-than-200% returns in the final 241-position book.

## Verified answer

Sub-10 target DTEs were included in training and scoring. The policy does not
require any sub-10 selections or impose a strict actual-expiry limit below ten
days. All variants compete by predicted EV; a longer DTE can win every slot.
There is no +200% ceiling on realized option returns and no removal of the
candidate book's top three winners from its headline result.

The final selection window contains 358 candidate rows with stored net returns
above +1,000%, including 331 sub-10-DTE rows. Of all 358, 356 fail EV >= 0.05;
the other two lose to higher-EV DTE variants of the same proposal. These are
stored historical labels, not independently quote-audited extreme fills.
Variants can repeat a market event; counts are rows, not independent trades.

## DTE funnel

| Target DTE | Final training rows | Final scored rows | EV >= 0.05 | Best EV DTE per proposal | Portfolio entries |
|---|---:|---:|---:|---:|---:|
| 1 | 593,336 | 85,315 | 93 | 7 | 0 |
| 2 | 32,180 | 5,020 | 0 | 0 | 0 |
| 4 | 32,143 | 5,006 | 0 | 0 | 0 |
| 5 | 590,439 | 84,632 | 357 | 71 | 0 |
| 7 | 31,883 | 4,930 | 0 | 0 | 0 |
| 10 | 558,333 | 78,312 | 1,194 | 362 | 0 |
| 30 | 406,265 | 56,201 | 12,561 | 10,021 | 125 |
| 45 | 366,988 | 53,348 | 11,099 | 8,674 | 116 |

All 78 sub-10 candidates remaining after DTE competition were rejected by
allocation: 43 encountered five occupied/reserved slots; 35 lost the available
slots to higher EV at the same signal timestamp. Slot reservation runs on the
underlying proposal entry/exit timeline; cash accounting later uses actual
recorded option-fill timestamps. No shorter-DTE quota/reserved slot exists.

After threshold and DTE comparison, 37 candidates still had stored net returns
above +200%. Allocation rejected all 37: 27 because five slots were reserved,
10 because higher-EV candidates took the free slots. The largest selected net
return is KWEB +177.133%; its gross return is +177.966%.

Examples from the saved predictions:

- IBM / TV support-resistance / July 10: 1-DTE stored net return +1,094.297%,
  EV +5.0838%; 30-DTE EV +9.6648%, so 30-DTE wins the proposal comparison.
  That 30-DTE candidate is then rejected because five slots are reserved.
- T / TV support-resistance / June 1: 10-DTE stored net return +1,603.216%,
  EV +5.1667%; 30-DTE EV +6.9247%, so 30-DTE wins the proposal comparison.
  That candidate loses the available slots to higher-EV same-time proposals.

## Active rules

- Standard target DTE grid `[1,5,10,30,45]`; `[2,4,7]` additionally enabled for
  15 frozen weekly symbols. No zero-DTE target. These are nearest-expiry targets,
  not exact expiry requirements (`nn_meta/config.py`, `weekly_expiry.py`).
- Contract search runs from `max(1,target_dte-10)` through `target_dte+20`
  calendar days, reads the previous date's chain, restricts strikes to raw spot
  +/-15%, then chooses nearest expiry and nearest ATM strike (`moneyness=0`).
  A 1-DTE target therefore does not guarantee an actual expiry below ten days
  (`nn_meta/decision_contracts.py`).
- Classifier label is `label_excess` (option net return beats contemporaneous
  underlying return). The chosen EV policy uses the signed-return regression
  output directly; it does not multiply it by classifier probability.
- Magnitude targets are clipped to training 1st/99th percentiles. Recomputed
  final bounds: -97.0730705% to +350.2203565%. Thus +500%, +1,000% and larger
  labels train the magnitude head as +350.2203565%; original labels stay intact.
- Final family is LightGBM, with Huber return regression (`alpha=0.5`) and L1
  validation early stopping; no sample weights are passed by this training path.
  40 member predictions are averaged. Tree settings: maximum 600 trees, learning
  rate .02, 31 leaves, minimum 200 child samples, L2 1.0, column fraction .8.
- Chosen EV threshold is .05. Among variants sharing symbol/strategy/trade index,
  only the highest EV survives. At each proposal entry time, highest EV fills
  free slots, one position per symbol, maximum five, up to 10% equity each.
  The final selected drawdown brake is `None`.
- Policy eligibility requires at least ten selected positions, maximum portfolio
  drawdown <=40%, and a return/drawdown ratio exceeding the frozen baseline's
  ex-top-three ratio, with a 5% drawdown denominator floor. Among eligible
  policies, highest validation portfolio return wins. This is a portfolio gate,
  not a 40% per-option stop or a cap on winning option returns.
- Ex-top-three remains an alternate baseline/comparison calculation. The
  headline candidate portfolio retains its winners. The 10% allocation cap
  limits account exposure, not individual option percentage returns.
- Proposal exits follow frozen underlying strategies and a 5% underlying-price
  stop. Take-profit and trailing-stop switches are off. There is no 200% option
  take-profit. Historical option entries/exits use option-bar opens/closes;
  every executed leg incurs .1% fees plus .05% slippage on each side. Up to 60
  rolls and 100,000 execution legs per variant are permitted. Maximum 2,000
  underlying proposals per symbol/strategy are built, as before.

## Comparison with retained versions

| Saved bundle | Selected mode | Magnitude target upper bound |
|---|---|---:|
| V3 | probability rank / .60 | No EV head in the selected policy |
| V3.1 | probability rank / .55 | No EV head in the selected policy |
| V4 | GBT EV / .05 | +358.0584% |
| V5 | NN EV / .05 | +373.5700% |
| Current V6 | GBT EV / .05 | +350.2204% |

The magnitude clipping policy was introduced in the August 21 V4 implementation,
not by the September 13 cash repair. Saved V4/V5 member parameters confirm their
bounds. V5's recorded source revision also already contains five slots, 10%
per-position allocation, 40% portfolio drawdown gate, 5% underlying stop,
disabled take-profit/trailing stop, and standard `[1,5,10,30,45]` DTE grid.
The risk gate dates to September 4. Candidate-side top-three retention is the
recorded August 24 decision. Do not attribute the V6 outcome to these being new.

V6 uses a newly rebuilt expanded feature/data contract, previous-date/raw-spot
contract selection and corrected mark/cash/roll accounting. The saved V5 bundle
has 48 features and selects NN; this V6 bundle has 164 and selects GBT. This
audit does not assign a numerical effect to any individual feature/data change.

## Evidence and verification

Reproduction script: `/tmp/healys-v6-selection-audit.py`.
Durable outputs: `nn_meta/validation/v6-selection-rules-audit-20260913/`:

- `audit.json`: hashes, exact checks and rejection counts.
- `training-dte-counts.csv`: full dataset and final training population.
- `selection-funnel.csv`: scores, threshold, DTE comparison and final entries.
- `allocation-rejections.csv`: rejection reason for each post-DTE candidate.
- `candidates-above-1000-percent.csv`: all 358 large-label rows and exclusion stage.
- `candidates-above-200-percent-after-DTE.csv`: all 37 remaining large-label rows.

Verified relevant current source hashes against the bound continuation scope and
training artifact hashes against completion receipts. Recomputed the exact
2,611,567-row final training population and both winsor bounds. The canonical
selection replay matches all 241 identities and size fractions; a separately
written allocation trace matches all 241 identities and accounts for every
post-DTE rejection. No retraining or counterfactual policy optimization occurred.
