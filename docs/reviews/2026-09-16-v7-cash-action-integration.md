# V7 reviewed cash-event integration

Reviewed corporate-action evidence now feeds the causal calculation code through
one whole-event compiler. The real run compiles **19 events from 40 provider
records**: eighteen Apple dividends and the corrected Devon fixed-plus-variable
distribution. Unreviewed inventory is retained explicitly. **V7 remains unready**;
these event checks do not establish complete histories or no-event intervals.

`nn_meta/v7/cash_actions.py` requires the review to replace every captured record
for that symbol and effective date exactly once. Partial replacement, duplicate
consumption, changed source records and concurrent split/complex actions fail.
The compiler never sums provider components into an already reviewed total.
Every event requires matching security IDs on the exact two adjacent eligible
exchange sessions and an observed Alpaca prior close at its captured session
close. Publication must precede the effective open. Cash units are explicitly
USD per common share. The output retains the review, consumed record identities,
prior close, conservative factor availability and typed `PriceAction` fields.

`scripts/compile_v7_cash_actions.py` verifies the inventory, normalized review
receipts, raw daily summary and all upstream input/code bindings. Conflicting
hashes from different parents fail before calculation. It partitions all 10,380
input records into 40 consumed and 10,340 still unresolved; no unreviewed event
is silently converted to an adjustment factor of one. No full-security admission
flag is set. A later complete builder still needs continuity and no-event proof.

## Actual retained evidence

All paths below are under `nn_meta/validation/`:

| Artifact | Result | Receipt SHA256 |
| --- | --- | --- |
| `v7-normalized-cash-reviews-20260916` | 19 exact event reviews; 425 bindings | `829317a8ebc8c2c94c4998a961f852cfe89662bdf78f486a2f1da5544a5369a3` |
| `v7-compiled-cash-actions-20260916` | 19 compiled actions; 432 bindings | `39d30518a6120edd5465e7ef2379846bcb68ef09dc6799fbd842a9ca5c9f83e3` |
| `v7-cash-event-returns-20260916` | 19 real return checks and 19 pre-event checks; 435 bindings | `894b4dc1cf6f401afd74e9904988fc03d300e73d50933e34fb695ebf5bba4c14` |

Normalization consumes the previously reviewed Apple issuer/news evidence and
Devon exception without adding new factual claims. The exact one-off source is
retained. Apple May 2023's news amount-only limitation remains; full issuer
record/pay dates are separately retained. No current-page historical version is
asserted. All eighteen Apple events use their observed previous Alpaca close.
Devon's four conflicting records resolve to one $0.44 cash event, prior close
$40.01 and factor 0.9890027493126718, matching the original reviewed correction.

Independent calculation uses 50-digit decimal arithmetic:
`current_raw_close / (prior_raw_close - reviewed_cash) - 1`. All nineteen results
match `causal_daily.returns`, maximum absolute error **5.915407053080912e-16**.
For every event, its preceding-day output equals both the no-action calculation
and the same prefix of the two-day calculation. These checks cover only the
reviewed adjacent dates, not the unreviewed remainder of either security.

Reproduction (new output directory required):

```bash
./venv/bin/python scripts/compile_v7_cash_actions.py \
  --inventory nn_meta/validation/v7-action-inventory-20260916r2 \
  --reviews nn_meta/validation/v7-normalized-cash-reviews-20260916 \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --calendar nn_meta/data_v7/start-20220315/calendar.json \
  --output nn_meta/validation/v7-compiled-cash-actions-20260916
```

Fourteen new regression cases passed. Full suite: **1,892 tests +18 subtests**,
18 warnings, 93.95 seconds. Retained log/source hashes:
`v7-cash-actions-tests-20260916`; original `/tmp/v7-cash-actions-tests.log`.
No production source changed after that run. All three evidence sets and their
upstream bindings reverified. All launched jobs are terminal; V6 untouched.
No new acquisition and no training launch. Eight substantive full-universe
readiness stages still require completion.
