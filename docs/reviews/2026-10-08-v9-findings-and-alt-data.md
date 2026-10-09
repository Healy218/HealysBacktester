# V9 findings and the alternative-data plan for earnings direction — 2026-10-08

Dated evidence and planning notes. Verdict tables live in [EXPERIMENTS](../EXPERIMENTS.md)
(the four V9 entries of 2026-10-08); this page summarizes what they mean together and
records the alternative-data survey that followed. It does not select work: that is
[TODO](../../TODO.md) and the user's call.

## 1. What V9 tested (all pre-registered, user-approved, run once)

| Test | Variants | Idea | Verdict | Key number |
|---|---|---|---|---|
| OEE-2 | 8 | ATM options through earnings: FA/TA/skew direction, IV run-up, cheap implied move | FAIL | Implied moves fair on average: \|move\| / implied = 0.99 / 0.97 / 1.00 by IV run-up tercile |
| OEE-H4 | 13 | OTM strangles and legs (5/10/20% OTM, cheap-leg filter, cheap vs own history) | FAIL | Means rise further OTM (20%: +61%/trade, 12% hit; 10% legs ≤ 0.5% of spot: +108%, 18% hit) but t ≤ 1.5 |
| OEE-J | 6 | FA score + old TA strategy pool (16 families, 2,840 variants) agreement choosing or tilting OTM legs | FAIL | TA vote sign accuracy 49.0%, FA 49.6% |
| OVE-3 | 9 | Unusual options buying, block calls, FINRA off-exchange short ratio (DIX), pre-earnings flow imbalance | FAIL | DIX near-miss (t 2.48, Holm 0.061) was market beta (−0.12% vs equal-weight universe); pre-earnings flow imbalance 47.9% sign accuracy |

36 variants, none passed. The one validated edge in the project remains **V8 H1 earnings
drift** (stock form passed the 2026 holdout; paper test from 2026-10-09).

## 2. What the results say

- **Direction is the missing piece.** Every free direction signal we built (prior EPS
  surprise vs own history, revenue acceleration, momentum, skew, 16 TA families, options
  flow) called the earnings reaction's sign 48–50% of the time.
- **Front-week earnings options are priced fairly before costs**, and measured spreads
  (4–6% near the money; 17–22% for cheap OTM) make every structure lose on average.
- **The lottery shape is real but unproven.** Cheap OTM options had positive means, carried by a few real
  shocks: SMCI 2024-01-18 (+35%; a 20% OTM call went $0.04 → $48, 89% of that variant's
  summed return), SNPS and ORCL 2025-09-09 (∓36%), SEDG 2023-10-19, AI 2025-08-08. Without
  each variant's top five trades, every OTM variant averaged −17% to −35% per trade. The
  user's "18% win rate → 420%" refers to these backtests: the 420% (H4e20, 12% hit) and the
  +271% (H4f 0.5%, 18% hit) are each carried by a handful of events, so their repeatability
  is unknown.
- **Copying unusual options buyers a day late loses** (−10% to −19% per trade): the
  information, if any, is priced by the next close.

## 2b. Correction (same day): the lottery wins were largely pre-announcements

The out-of-sample test of the user's payoff thesis (20% OTM legs, both sides, half Kelly)
first passed, then a check of its top event found IBM 2026-07-14, an unscheduled
pre-announcement. Many of the biggest OTM winners were such pre-announcements:
SMCI 2024-01-18, SEDG 2023-10-19, AI 2025-08-08 and IBM 2026-07-14. You cannot know their dates
ahead, so they are not tradeable. With them removed, the pooled out-of-sample mean is +1.3% per
leg (−7.4% at 1.5× costs, −9.6% without the best event): **FAIL**. 10% legs lose everywhere.
Details: [EXPERIMENTS](../EXPERIMENTS.md), last entry. Implication: the payoff structure alone
is not an edge on scheduled earnings; a direction or magnitude signal is required, which keeps
the alternative-data plan below as the main path.

## 3. Why there is no edge in this data (the professionals' advantages)

1. **Information.** Free daily data is what everyone has, so it is priced. Funds buy signed
   tick-level option trades, point-in-time analyst consensus and revisions, and alternative
   data (card spending, app downloads, web traffic, satellite) that reveal the quarter
   before the call.
2. **Execution cost.** Their edges are basis points per trade; retail spreads on short-dated
   options are several percent. Our short iron fly was −5% gross and −58% net.
3. **Breadth.** Hundreds of weak signals (about 51% accuracy each) across thousands of
   names, combined. Such signals are invisible to an 800-event t-test and too small for
   retail costs.
4. **Being the house.** Market makers and volatility sellers collect the spread and the
   variance risk premium; retail OTM buyers usually pay it.

Retail advantages: small size (no capacity limit), patience (slow effects such as earnings
drift, where costs are small relative to the move), no career risk (can wait for rare
payoffs), and the same research discipline.

## 4. Alternative data for earnings direction — survey (probes run 2026-10-08)

The test for every source: **point-in-time history covering 2022–2025** (needed to
backtest), not just today's values.

| Source | Cost | History | What it gives | Use |
|---|---|---|---|---|
| **Benzinga headlines in our Alpaca news archive** (`v8-events-20261008-r0/news/news.parquet`, 357k rows, 2021-01 → 2025-12) | free, already on disk | 2021–2025 (2026 fetchable) | analyst actions: 14,631 price-target raises, 9,426 cuts, 4,648 upgrades, 4,413 downgrades, 25,911 "maintains"; 2,513 earnings headlines with **consensus EPS and revenue estimates** | analyst-revision momentum before the release (strongest literature predictor of the surprise); prior-quarter surprise vs consensus |
| **Alpha Vantage EARNINGS** (`ALPHAVANTAGE_KEY`) | free, 25 requests/day, 1/s | back to 1999 (NVDA 110 quarters, AMD 122) | reported EPS, consensus estimated EPS, surprise %, report time (pre/post-market) | consensus-surprise history and streaks; validates the headline estimates; ~5 days of a daily job for the pool |
| Finnhub insider sentiment (`FINNHUB_API_KEY`) | free | monthly from 2015 | MSPR insider purchase ratio | complements our own Form 4 table (`insider/insider.parquet`) |
| Finnhub earnings, recommendations | free | last 4 quarters / 4 months only | — | forward use only |
| Finnhub estimates, upgrades, price targets, social sentiment | paid (403) | — | — | not available |
| Stocktwits sentiment and message volume (claude.ai connector) | free | weekly for the last year, monthly before | crowd sentiment | too coarse for a pre-release week historically; forward recorder candidate |
| Wikipedia page views (`wiki/pageviews.parquet`) | free, on disk | 2021–2025 daily | attention | magnitude (big-move) predictor for strangles rather than direction |
| Google Trends | free (unofficial API) | weekly 5y; daily in 90-day windows | search attention | same as Wikipedia; stitching needed |
| FINRA short interest (bi-monthly) | free | years | short interest change before the release | direction candidate (crowded shorts) |
| Card spending, app downloads, web traffic, satellite | paid | — | the quarter's actual sales | the professional edge; only if free evidence justifies a subscription |

## 5. Proposed next step (for the user to approve)

- **ALT-0 — coverage only.** Per OEE event, add point-in-time features:
  - analyst actions in the 30 and 90 days before the entry day (net price-target raises
    minus cuts, upgrades minus downgrades, the size of target changes);
  - prior-quarter surprise vs consensus (headlines, cross-checked with Alpha Vantage);
  - the consensus estimate's implied growth vs the year-ago actual;
  - insider net buying (Form 4) over 90 days;
  - FINRA short-interest change;
  - attention abnormality (Wikipedia).

  Report coverage only.
- **ALT-1 — pre-registration (user sign-off).**
  - **Direction:** revision momentum and consensus-beat persistence pick the side of the
    OTM leg or ATM option.
  - **Magnitude:** attention and dispersion of analyst actions select events for cheap OTM
    strangles. The strangle needs a big move, not a direction.

  Dev 2023–2025 as before; 2026 confirmation after fetching 2026 news.
- In parallel: an Alpha Vantage daily job (25 tickers/day) to pull consensus history for
  the pool, and a Stocktwits forward recorder if the user wants crowd sentiment going forward.
