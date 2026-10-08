# TODO — V9 options experts (OEE first)

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
- [ ] **OEE-1 (next):** pre-registration (direction score from prior SUE / revenue trend /
  momentum / skew; IV run-up vs move size — the user's observation; implied move vs
  own earnings history); user sign-off.
- [ ] **OEE-2:** walk-forward (dev 2022-03 → 2025-12), then a 2026 confirmation.
- [ ] **OEE-3:** paper forward test with half-Kelly and the drawdown brake.

## OVE — Options Volume Expert

- [ ] **OVE-0:** confirm free per-contract daily volume and open interest from Alpaca;
  start a daily open-interest recorder (forward-only data, so start early).
- [ ] **OVE-1..3:** noise-filtered unusual options buying (abnormal volume, block size,
  short-dated OTM premium, no event, clustering) and DIX-direction off-exchange flow;
  pre-register; walk-forward.

## Running

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
