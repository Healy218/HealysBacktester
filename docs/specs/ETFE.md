# ETFE — Exchange Traded Funds Expert

A brand-new expert selected October 3, 2026, replacing V7 as the active research
priority. It reuses V7 strategy/timing specifications, not V7 model identity,
trained weights or checkpoints. Implementation, data admission and training
remain open.
[ROADMAP](../../ROADMAP.md#etfe--exchange-traded-funds-expert) owns the gates;
[TODO](../../TODO.md) owns current actions.

## Accepted scope

| Dimension | ETFE contract |
| --- | --- |
| Tradable underlying universe | Exactly **SPY, QQQ, VOO**, including their eligible option contracts |
| Strategies | All V7 strategy families and parameter variants; no winner-only selection |
| Signal bars | **1, 5, 15 minutes**; restore 1-minute signals and remove 30-minute signals |
| Execution observations | Retain V7's **one-minute** cadence and event-time quote chronology |
| Timing and risk | Inherit V7's accepted entry, exit, DTE, roll and expiry rules below |
| Historical start | **Alpaca’s earliest historical options availability**; exact first timestamp to be verified from provider data, not our own recording start |
| Historical end | **October 2, 2026, inclusive**, fixed by the user |
| Options provider | **Alpaca only; no Massive quotes**, including archived quotes or fallback requests |
| Research identity | New ETFE manifests, catalog, features, labels, folds, checkpoints and model artifacts |

Here, the user's “1 minute ticks” and “30 minute ticks” mean signal-bar
timeframes. Event-level option quotes/trades remain separate required inputs;
one-minute bars do not reconstruct those events. Other V7 settings remain
inherited unless an explicit ETFE decision changes them.

The fixed three-ETF universe is a user-selected research scope, not a claim of
market-wide representativeness. Market/context instruments required by inherited
features are inputs, not additional tradable candidates. Keep separate SPY and
VOO identities and account for correlated positions using the inherited shared
capital rules. Do not assume identical option listings or liquidity.

## V7 inheritance and precedence

Use the [V7 scope](MULTITIMEFRAME_RESEARCH.md) together with its accepted
amendments. The base document's original ask/bid execution description is
superseded by the [arithmetic-midpoint/risk amendment](V7_OPTION_RISK_20260916.json).
ETFE changes the universe, signal timeframes, provider/history boundary and
research identity; it does not revert later accepted V7 execution rules.

- Keep all 20 families: `bbands`, `bbw_squeeze`, `elliott`, `keltner`, `ma`,
  `macd`, `rsi`, `squeeze`, `stoch`, `supertrend`, `tv_amd`, `tv_fibonacci`,
  `tv_gaussian`, `tv_msb`, `tv_rating`, `tv_rsi_probability`, `tv_setup`, `tv_sr`,
  `tv_uptrick`, `volume`. Inherit their registered grids and direction semantics.
- V7's inventory has 2,817 parameter variants per timeframe. At unchanged grids,
  ETFE has an expected 8,451 variant/timeframe combinations per ticker and 25,353
  across three tickers. This is planning arithmetic, excluding directions, DTE
  targets, contracts, events and model trials; the new catalog must verify it.
- Retain actual **1–9 calendar DTE** at every purchase, targets **1/5** and the
  declared weekly **2/4/7** subset. Zero DTE remains excluded. Preserve exact
  family eligibility rather than applying every target to every family.
- Signals become available at completed bar close; use session-aligned bars,
  actual calendars, DST and early closes. Revalidate 1-minute warmup and higher
  timeframe context; the old 5/15/30 schema is not an ETFE schema.
- Retain **1-second latency**, **60-second entry deadline**, **30-second quote
  maximum age**, positive valid bid/ask and minimum reported size of one.
- Simulated option buys, sells and marks use **(bid + ask) / 2** from a valid
  fresh quote. Keep **0.10% fee + 0.05% slippage per side**. A simulated midpoint
  is not a guaranteed broker fill; last trades and OHLCV are not quote substitutes.
- Retain the **12.5% option-premium stop** per purchased leg and underlying
  strategy exits; do not restore the superseded generic 5% underlying stop.
- Retain ITM expiry exit **15 minutes before the dated option-class regular
  close**, including early closes. Preserve OTM rolls and
  [funded physical exercise/stock liquidation](V7_PHYSICAL_EXPIRY_20260915.md).
  Bind actual dated hours for these ETF option classes; do not assume a universal
  close or substitute V6's later ten-minute entry window.
- Preserve full features, including all thirteen TradingView scopes and option
  quote/trade fields. Audit ETF applicability and availability; any change to
  feature semantics needs an explicit decision and a new schema.
- Preserve the [evaluation policy](V7_EVALUATION_20220315_PHYSICAL.json): shared
  five-slot portfolio, 10% equity fraction, chronological walk-forward evaluation,
  complete exit/roll/stock-settlement horizon purging, ten-session embargo,
  train-only fitting, baseline comparisons and full trial accounting. Re-declare
  fold dates for ETFE's shorter history before selection; old calendar boundaries
  and previously inspected outcomes are not a new untouched holdout.

V7's [September 20 timeframe amendment](../reviews/2026-09-20-v7-timeframe-scope-amendment.md)
continues to describe V7. Its 1-minute removal is explicitly reversed only for
ETFE, which also removes 30-minute signals. No V7 manifest is edited or relabeled.

## Alpaca history boundary and evidence gap

Checked October 3, 2026: Alpaca's
[historical options documentation](https://docs.alpaca.markets/us/docs/historical-option-data)
states availability since **February 2024**, without an exact first timestamp.
That month is a provider-history lead, not a sealed February 1 start date.
The same documentation distinguishes subscribed OPRA observations from the
indicative feed; indicative values do not establish the inherited observed-quote
contract.

The [documented options client](https://alpaca.markets/sdks/python/api_reference/data/option/historical.html)
lists historical trades/bars and latest quotes/snapshots, but no historical quote
window method. The project's [October 2 provider review](../reviews/2026-10-02-v6-alpaca-provider.md)
also records a historical-quotes endpoint probe returning 404. This is an
identified coverage gap, not proof that three tickers solve quote history.

The user confirmed both date choices: start at Alpaca's earliest options
history and end October 2, 2026, inclusive. No date preference question remains.
Before sealing executable timestamps, record:

1. Alpaca's exact first historical options timestamp from provider evidence.
   This is a data-verification task, not permission to substitute our recording
   start or a later date with easier feature coverage.
2. Actual first usable timestamps and gap coverage for SPY/QQQ/VOO minute data,
   option trades, required bid/ask windows, dated contract metadata, calendars
   and all feature dependencies, with feed/entitlement and source receipts.
3. The nominal history boundary separately from each feature's first eligible
   observation. Preserve the inherited causal warmup rule, with no fabricated
   pre-start labels. Earlier warmup history needs an explicit ETFE policy.
4. The October 2, 2026 final session boundaries from the captured exchange
   calendar and dated instrument hours, expressed in UTC. Include that session;
   do not advance the end when the plan is frozen or while a campaign runs.
   Labels still need complete observed exit/roll/settlement horizons: boundary
   proposals whose outcomes require data after October 2 must be explicitly
   censored or ineligible under the declared evaluation policy, never assigned
   invented outcomes or used to extend the user's data window silently.

Massive quotes are excluded by explicit user direction. Do not request new
Massive quotes, read archived V7 Massive quotes into ETFE, blend them with Alpaca
quotes, or offer them as an automatic fallback. V7 archives remain preservation
artifacts for V7 only.

If Alpaca cannot supply required historical bid/ask observations, record the
specific gap under ETFE.provider-contract. Any necessary execution/feature
methodology change must be explicit; trade bars do not establish observed
spreads. Do not silently drop quote features, move the start or end, or claim
that preserving V7 strategy/timing rules proves identical data availability.

## Implementation boundary and resource plan

This session sets up notes and docs. No ETFE data campaign, model training,
paper deployment, subscription purchase or runtime switch is authorized by a
documentation milestone. ETFE needs its own admission evidence; V7 component
results may be referenced only within their demonstrated scope.

Before acquisition/build, inventory reusable inputs and run a bounded resource
pilot. Measure one-minute event density, quote demand, peak memory and disk
growth, including the busiest ticker; three ETFs do not imply one-hundredth of
V7's quote volume. Use bounded streaming, shared request deduplication and the
project autosizer. Bind a storage budget to measured free space and keep recovery
checkpoints. Do not reload the entire V7 archive to establish a new catalog.

V7 remains preserved separately under MRHA/v7. Finish its already-authorized
archive verification independently; its research gate 7-3 is not closed by
ETFE's selection. The [archive README](../reference/V7_COLD_ARCHIVE_README.md)
and [last V7 research handoff](../../handoff-history/HANDOFF-2026-10-02-before-v7-cold-archive.md)
remain restoration references, not orders to resume V7.
