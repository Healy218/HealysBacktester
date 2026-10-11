# TODO — next: model the user's own market view (V9 closed, no edge)

## NEXT — the user's market view (Monday 2026-10-12)

- [ ] Interview the user about the edges they have won on (setups, signals, sizing, exits,
  decay); write a dated spec; split testable rules from judgment calls
  ([HANDOFF](HANDOFF.md)).
- [ ] Pre-register the testable rules (V8/V9 discipline), then model the judgment calls.
- [x] **UV1 midday fade** (user idea 2026-10-11): at 10:30 Central fade a < 1% morning move in
  SPY/QQQ with first-OTM 0DTE options or stock, hold 2 hours, by weekday. FAIL, 48 variants, no
  positive cell; no midday reversal (gross −0.6 to −1.3 bp) ([spec](docs/specs/UV1_MIDDAY_FADE_PREREG_20261011.json);
  [EXPERIMENTS](docs/EXPERIMENTS.md)).
- [x] **UV2 one-hour scan** (user direction 2026-10-11): UV1's rule at every entry minute,
  fade and follow, by weekday (30,240 cells, permutation null). FAIL: both family-wise outliers
  lost in 2026 ([spec](docs/specs/UV2_HOUR_SCAN_PREREG_20261011.json); [EXPERIMENTS](docs/EXPERIMENTS.md)).


**Selected work: [V9 plan](docs/specs/V9_OPTIONS_EXPERTS_PLAN_20261008.md)** (user
direction 2026-10-08): options-native, short-term, high-risk/high-reward; fractional
Kelly with 10–20% downside caps. Rules carried from V8: pre-register before examining
any signal-return relationship; measured option costs (0–15 DTE spreads 4–6% of mid);
Kelly only from out-of-sample trade statistics; no paid data unless paper evidence
justifies it. Run large jobs under `systemd-run --user --scope -p MemoryMax=…`, with
worker pools and vectorized code by default.

## OEE — Options Earnings Expert

- [x] **OEE-0:** event table — 1,354 earnings 8-Ks, 1,330 usable (2026-10-08;
  [state](docs/CURRENT_STATE.md#v9-plan-october-8)). Coverage only.
- [x] **OEE-1:** pre-registration approved by the user and frozen 2026-10-08:
  [V9_OEE1_PREREG_20261008.json](docs/specs/V9_OEE1_PREREG_20261008.json) (8 variants).
- [x] **OEE-2:** FAIL, all 8 variants (2026-10-08;
  [EXPERIMENTS](docs/EXPERIMENTS.md)). IV run-up did not predict move vs implied;
  2026 confirmation not run.
- [x] **OEE-H4** (OTM options, user's thesis): FAIL, 13 variants, lottery-shaped: cheaper/further
  OTM had higher means carried by a few real shocks, t ≤ 1.5 (2026-10-08; [EXPERIMENTS](docs/EXPERIMENTS.md)).
- [x] **OEE-J** (FA score + TA-pool agreement choosing/tilting OTM legs): FAIL, 6 variants;
  TA vote 49% sign accuracy (2026-10-08; [EXPERIMENTS](docs/EXPERIMENTS.md)).
- [ ] ~~OEE-3~~ not reached (no pass). Next OEE step is the user's call: see HANDOFF.

## OVE — Options Volume Expert

- [x] **OVE-0:** Alpaca free tier confirmed (contract OI with its as-of date, daily option
  bars with volume/trades, indicative snapshots); OI recorder timer running from
  2026-10-08 (08:00 and 18:00 ET).
- [x] **OVE-1:** flow + dark-pool table, coverage only (2026-10-08;
  [state](docs/CURRENT_STATE.md#v9-plan-october-8)).
- [x] **OVE-2:** pre-registration approved and frozen: [V9_OVE2_PREREG_20261008.json](docs/specs/V9_OVE2_PREREG_20261008.json) (9 variants).
- [x] **OVE-3:** FAIL, 9 variants (2026-10-08; [EXPERIMENTS](docs/EXPERIMENTS.md)). Near-miss B1
  (DIX long, t 2.48, Holm 0.061) is market beta: −0.12% vs the equal-weight universe.

- [x] **OTM payoff out of sample** (user thesis): FAIL after excluding unscheduled pre-announcements
  (pooled OOS +1.3%/leg, −7.4% at 1.5×) (2026-10-08; [EXPERIMENTS](docs/EXPERIMENTS.md)).

## ALT — alternative data for earnings direction (user direction 2026-10-08)

Notes and source survey: [V9 findings and alt-data plan](docs/reviews/2026-10-08-v9-findings-and-alt-data.md).
- [x] **ALT-0:** per-event features built, coverage only (2026-10-08; [state](docs/CURRENT_STATE.md#v9-plan-october-8)).
  To do: extend news/insider/Wikipedia through 2026-09 for a 2026 confirmation; Alpha Vantage pull.
- [x] **ALT-1:** pre-registration approved and frozen: [V9_ALT1_PREREG_20261008.json](docs/specs/V9_ALT1_PREREG_20261008.json).
- [x] **ALT-2:** FAIL, 8 variants; direction accuracy 46.8–49.7% (2026-10-08; [EXPERIMENTS](docs/EXPERIMENTS.md)).

## Running

- **Alpha Vantage consensus pull** `healys-v9-alphavantage.timer` (daily, ~7 days to complete).

- **OI recorder** `healys-v9-oi-recorder.timer` → `nn_meta/data_cache_v9/open_interest/`
  (`journalctl --user -u healys-v9-oi-recorder`); a failed run loses that snapshot.

- **V8 H1 paper test** in "stonks bot 2" (PA3U9D8Q8GQX): stock + ~45 DTE call per
  earnings-drift signal; timers 09:45 / 10:31 / 16:20 ET from 2026-10-09. Review after
  the first earnings wave (fills vs decision quotes; call vs stock per signal):
  `./venv/bin/python scripts/run_v8_h1_paper.py status`.

## V8 outcome (complete; details in [EXPERIMENTS](docs/EXPERIMENTS.md))

Stage 0 contract frozen; stage 1 (5,680 long-only price variants) and stage 2 (vol
timing) failed; event hypotheses failed except H1 earnings drift (SUE, 20-day, long),
which passed the 2026 holdout in stock form; its calls form was inconclusive at
pessimistic costs; the short side, long-short and puts failed.

## Parallel / later (not started)

- FA fundamentals point-in-time features beyond EPS (the V8 events backfill has all
  as-filed XBRL facts 2019+).
- V6 paper runtime: retired by the user 2026-10-08 (needed the cancelled paid feed).
