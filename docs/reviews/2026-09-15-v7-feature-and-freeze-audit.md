# V7 feature inventory and pre-freeze audit

Reviewed ROADMAP.md, TODO.md, GOALS.md, the current multiple-timeframe spec,
REALTIME_SPEC, V7 preparation reviews, September 12 training notes, and the
actual V7 feature/row/execution/pilot code. This is the current checklist;
earlier dated reviews remain historical evidence.

**Verdict: feature inventory is largely present, but V7 is not ready for
freeze/build/training.** Several required behaviors are still missing from
the integrated engine. Passing component tests does not close those gates.

## Accepted run scope

- March 15, 2022 through September 14, 2026, inclusive.
- March 8–14 removed from active working inputs; original captures archived.
- Alpaca Algo Trader Plus underlying stocks; Massive historical options.
- All 20 strategy families, 2,817 variants/timeframe, **11,268/ticker** across
  1/5/15/30-minute signals. No global winner-only freeze or 2,000-event cap.
- One-minute observed bid/ask execution/marks, actual 1–9 calendar DTE for
  every purchase. Target choices 1/2/4/5/7, subject to dated weekly eligibility.
- Five shared slots, 10% equity allocation, one symbol across timeframes,
  cash reservation, explicit latency/spread/fees/slippage.
- Latest expiry choice: funded physical exercise/stock delivery and observed
  stock liquidation. Missing prerequisites still block affected evaluations.
- Four bounded workers, shared 250 GB decimal acquisition cap, existing V6
  paper runtime protected. No full campaign launched.

## Feature inventory: no entire agreed group was silently dropped

The model-row schema in `nn_meta/v7/rows.py` currently has **222 columns**:

| Group | Columns | Implementation/evidence | Remaining work |
|---|---:|---|---|
| Technical, returns and session clock | 15 | `features.py`, `context.py`; parameter-specific MA fields | Causal-price integration and post-deletion warmup |
| Daily volatility, IV, term structure, put/call ratio, market context, beta | 10 | `daily.py`; real SPY pilot only | Every eligible security, raw-spot/causal-return basis, fresh prior-date context |
| Direction, DTE, moneyness, signal spacing | 4 | `rows.py` | Resolve target-DTE scaling and constant moneyness conventions below |
| Strategy identity | 20 | All family adapters/catalog and local parity tests | New-window integrated verification |
| Sector identity | 9 | Schema accepts explicit sector or unknown | Frozen dated mapping for complete historical universe |
| Thirteen TradingView source scopes | 96 | Registered projections, local prefix/timeframe tests and old-window pilot | New causal inputs and new-window full-row validation |
| Option quote/trade features | 10 | `tick_features.py`; exact receipt-bound joins in old SPY pilot | Full required quote/trade capture and condition coverage |
| Timeframe identity | 4 | 1/5/15/30 one-hot fields | Full assembly verification |
| Numeric parameter values | 48 | Registered parameter keys, nonapplicable values remain missing | Full assembly/training adapter |
| Setup identity | 6 | VWAP/EMA/BRT/SWEEP/DIV/ORB | Full assembly verification |

The thirteen sources are Gaussian (6 columns), Fibonacci (6), Uptrick (5),
Emre structure (5), support/resistance (6), RSI probability (7), ICT (16),
volume-weighted order blocks (6), AMD (6), Setup Scanner (15), structural
liquidity/POC (6), HTF log-regression profile (7), and scoped footprint (5).
Keltner and BBW strategies are also present in the twenty-family catalog.

The ten tick columns cover spread, size imbalance, valid-quote fraction,
quote age, update rate, trade-count rate, volume rate, trade-VWAP versus mid,
signed-volume fraction and classified-volume fraction. The original source
scopes and native-footprint limitations remain explicit.

## Required work before declaring the run ready

1. **Rebuild the PIT universe after date deletion.** Current coverage counts
   use the old membership diagnostically. `universe.membership` correctly
   rejects missing calendar sessions today; teach the builder the explicit
   exclusion policy, with documented lookback treatment and regression tests.
   Do not silently delete exchange-calendar dates or reuse rankings that used
   the removed option days. Complete session aliases, listing/delisting/halts,
   reused identities and frozen sectors. There are 122 remaining zero-session
   cases in the provisional new-date inventory, mostly lifecycle cases.
2. **Finish causal corporate-action prices.** `causal_prices.py` is a tested
   prototype, not connected to the production feature/proposal path. Supply
   dated split/dividend/spin-off evidence, contemporaneous tick units and
   cross-action stop accounting. Current vendor all-adjusted prices are not
   historical-vintage proof. Declaration dates alone do not prove dividend
   amounts were known at those dates.
3. **Complete daily/context features for all securities.** The existing real
   daily pilot is SPY-only. Wire security-bound market/sector histories and
   explicit missingness. Restart price-feature state March 15 after deletion;
   record actual first eligible observations for each feature. A 60-session
   beta cannot be claimed available from a cold start. Do not silently move
   the requested research start, impute invented history, or omit columns.
4. **Resolve two model-input conventions before sealing.** `FeatureRows.row`
   currently stores `target_dte / 45` and `moneyness = 0`. These preserve the
   legacy baseline convention; they are not the selected option's actual DTE
   and strike-to-raw-spot distance. Implement actual contract fields, or
   explicitly freeze and name the intended baseline semantics with a fair
   comparison. The actual-1–9-DTE execution check alone does not fix model inputs.
5. **Implement physical expiry.** The latest choice is declared only.
   `replay.py` still returns `expiry_liquidation_unresolved`; `CashLedger`
   contains option buy/sell events, not an exercise/stock ledger. Add shared
   funding/share delivery, dated settlement, stock quote liquidation/marks,
   costs, fractional-paper treatment and complete label horizons. See the
   physical-expiry spec. Never infer a terminal return from absent bids.
6. **Finish historical option rules and actual capture.** Validate class-specific
   closes/early closes and weekly listing eligibility. Generate actual
   proposal/feature/roll/exercise interval unions on the new scope, measure
   representative retained densities and complete capture under 250 GB.
   Broad 76-million-quote-hour demand from the old scope is not a feasibility
   proof. The March 7 SPY tick store is historical and cannot cover the new pilot.
7. **Finish bounded full-history assembly and training integration.** Factorized
   rows and fold-indexed LightGBM Sequence have unit/pilot evidence only.
   Connect all full-history labels, marks, memberships and rows; test the
   library's binned-dataset memory, peak workers, disk usage and recovery under
   concurrent V6 load. Do not use old 164-column/V6 campaign assumptions with
   the new 222-column schema. The catalogue is not an executable training pipeline.
8. **Freeze the complete training/evaluation trial manifest.** Chronological
   folds, embargo and train-only fitting are declared; V7 model families,
   objectives, seeds, weighting, calibration, thresholds and trial accounting
   are not a complete runnable campaign yet. Carry forward baseline comparisons,
   finite NN/GBT checks, deterministic seeds, cost/latency/ex-outlier diagnostics,
   PBO/deflated-Sharpe reporting and reproducibility from existing infrastructure.
   Event-balanced and downside-quantile experiments already exist for V6;
   explicitly decide their V7 trial status before outcomes, rather than assuming
   they are connected to factorized rows. No automatic promotion of complexity.
9. **Run new-window integrated/resource pilots and one launch gate.** Include
   sparse/liquid markets, early closes, aliases/actions, rolls and funded expiry.
   Require complete source/runtime/input hashes and end-of-run mutation checks.
   Build a single executable complete-universe readiness report; the current
   `test_v7_readiness.py` tests components, not a whole-campaign launch gate.

## Deliberately deferred or separate — do not expand this run implicitly

- External TradingView/Pine comparison was explicitly deferred. Keep all
  thirteen local scopes and mark parity unverified; native footprint/intrabar
  modes were never admitted into this scope.
- The old REALTIME_SPEC's 15-minute-only V7 cadence is superseded by the
  1/5/15/30-minute research spec. Its live/offline-twin requirement still applies
  before live deployment. Examples such as new bar-shape/trade-acceleration
  features are future candidates, not extra promised columns in the 222 schema.
- Learned contract selection/exits, direct ranking, extra regime/breadth inputs,
  uncertainty abstention and wider event weighting are later research in the
  training notes; they have not been silently declared current-run requirements.
- HAR-RV/GARCH/sequence volatility experts, SPX0, FA news/fundamental overlays,
  stacking and RL remain separate roadmap workstreams with their own evidence
  gates. They are not missing pieces of the accepted V7 feature inventory.
- Dashboard deployment, continuous V6 evidence collection and the first-week
  maturity review (on/after September 21) remain operations work. Sustain the
  existing runtime; do not turn this preparation checkpoint into a deployment.

## Verification and next-session instruction

Date migration: 7,430 stock shards; 2,226,484 raw/adjusted rows excluded; an
independent scan of all 1,238 year-2022 shards found zero forbidden rows.
New contract catalog: 22,130,242 contracts. Full regression suite:
**1,722 tests and 18 subtests passed**, 82.54 seconds; 18 warnings recorded in
`/tmp/v7-march15-final-tests.log`.

The next session should read TODO then HANDOFF and complete the ordered gates
above. It must not interpret a clean session, passing tests, completed base
acquisition or this documentation audit as permission/evidence to skip them.
