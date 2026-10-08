# V9 — Options experts: OEE (earnings) and OVE (options volume)

Planned 2026-10-08 with the user. V9 is the options-native phase the user asked for:
short-term, high-risk/high-reward, fractional-Kelly sizing with 10–20% downside caps.
It reuses everything V8 built and keeps V8's discipline, because that discipline is
what separated the one real edge (H1 earnings drift) from a long list of artifacts.

## Ground rules carried from V8

- **Pre-register before looking.** Data steps may report coverage only. No
  signal-to-return relationship is examined before the hypothesis, variants, folds and
  pass rules are frozen and committed.
- **Measured costs.** Option fills at mid ± k × measured half-spread (k = 1.0 primary,
  1.5 stress) from the V8 spread table. OEE and OVE trade 0–15 DTE contracts, exactly
  where V7 captured 386k near-the-money quotes (median spread 4–6% of mid).
- **Kelly sizes an edge; it never creates one.** Tests use fixed risk per trade.
  Fractional (half) Kelly is set afterwards from out-of-sample trade statistics only,
  with per-position and total-premium caps and a portfolio drawdown brake (halve
  sizing at −15%, stop new entries at −20%). Per-trade risk is the premium paid
  (defined risk); no tight premium stops (they bled V6 on spreads).
- **Free data first.** No subscription unless paper evidence justifies it.
- **Holdout.** The 2026 window (to 2026-09-14) was used once, for H1 stock. OEE/OVE
  trade different events, so 2026 can still confirm a winner, recorded as partially
  used. Forward paper trading is the final gate.

## Reused V8 assets

PIT pool with delisted names (`docs/specs/V8_POOL_PIT2021_20261007.json`), bars and
admission (`V8_CONTRACT_20261008.json`), option chains 2021-01 → 2026-09-14 for every
pool name (`nn_meta/validation/v8-stage2-20261008-r0/chains/`), IV30 / HAR panel,
option spread table (`v8-spreads-option-20261008-r0/model.json`), the events backfill
(`v8-events-20261008-r0/`: 8-K earnings acceptance times, as-filed XBRL facts,
insider, FINRA short/off-exchange volume, news, Wikipedia views), the numba engine,
`nn_meta/v8_vol.py` (Black-76, parity forwards), `nn_meta/v8_h1_calls.py` (contract
picking and exits) and `nn_meta/v8_parallel.py`.

## OEE — Options Earnings Expert (first)

The user's thesis: the biggest moves happen when unknowns become known. The open
question is how to weigh calls versus puts (and how hard to press) using the full
FA/TA/options picture before the release.

**Event:** each earnings release (8-K Item 2.02, acceptance time). Entry at the last
close before the release (after-close release on day D → enter at D's close; pre-market
release on D → enter at D−1's close). Exit at the close of the reaction day. Assumption
to state in the pre-registration: the release date is known at least 5 trading days
ahead (companies announce dates weeks in advance; our data records only the release).

**Hypotheses to pre-register (OEE-1):**

| ID | Question | Inputs (all PIT) | Trade |
|---|---|---|---|
| OEE-H1 direction | Does a pre-release direction score predict the sign of the reaction? | prior-quarter SUE (surprise persistence, Bernard & Thomas 1990); revenue/margin trend from XBRL; price momentum and pre-release drift; option skew (put vs call IV; Xing, Zhang & Zhao 2010) | calls if the score is positive, puts if negative; nearest expiry after the release |
| OEE-H2 IV run-up (user's observation) | Does a large IV build in the week before earnings precede a smaller move relative to the implied move, and a small build a bigger one? | ATM IV change over the 5 trading days before entry; implied move from the front straddle | long straddle when the run-up is low; no trade (or defined-risk short) when high |
| OEE-H3 cheap move | Is the implied move cheap versus the stock's own past earnings moves? | implied move ÷ trailing median realized earnings move (PIT) | long straddle / directional option when cheap |

Sizing for the test: fixed premium per event; Kelly afterwards from OOS stats.
Evaluation: dev 2022-03 → 2025-12 (expanding, six half-year folds as V8), pass rules
in the V8 style (positive in ≥ 4/6 folds, mean trade return t ≥ 2, deflated Sharpe,
1.5× cost stress; for H2 a monotone relation between run-up bucket and realized/implied
move). Universe: pool names with earnings 8-Ks and listed weekly options.

**Stages:** OEE-0 event table (pre/post option prices, implied move, IV run-up, skew,
realized move, coverage report — no outcome analysis) → OEE-1 pre-registration (user
sign-off) → OEE-2 walk-forward + 2026 confirmation → OEE-3 paper (stonks bot 2 or a
third paper account) with Kelly sizing.

## OVE — Options Volume Expert (second)

**Question:** can unusual options buying, cleaned of noise and optionally confirmed by
off-exchange (dark-pool) flow, predict 1–5 day moves tradable with short-dated calls?

**Noise filters (historical, from OPRA daily aggregates):** volume vs the contract's and
the underlying's own history; average trade size (volume ÷ transactions; block-size
prints); short-dated OTM with large premium dollars; no earnings within N days and no
large prior stock move; clustering across strikes/days; option close near its high with
a flat stock. **Forward-only:** open-interest change (opening vs closing), recorded daily
from Alpaca's free contracts endpoint starting as soon as possible.

**Dark pools:** FINRA daily off-exchange short/total volume (already backfilled
2021–2025; the DIX source) and FINRA weekly per-venue ATS volume (free). Note: V8 H3
went long the lowest off-exchange short ratio; the DIX reading is the opposite (high
off-exchange short volume = market makers filling buys). Test the DIX direction as its
own pre-registered hypothesis, alone and as a confirmation filter for options flow.

**Stages:** OVE-0 live-data check (does Alpaca's free tier give per-contract daily volume
and OI going forward?) and an OI recorder → OVE-1 flow and dark-pool tables (coverage
only) → OVE-2 pre-registration → OVE-3 walk-forward → OVE-4 paper.

## Order of work

1. OEE-0 (data, coverage only).
2. OVE-0 OI recorder (small; every day not recorded is lost) and live-data check.
3. OEE-1 pre-registration with the user, then OEE-2.
4. OVE-1..3.
Meanwhile the V8 H1 paper test runs (stock + call per signal); its fills calibrate real
option costs for both experts.
