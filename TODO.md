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
- [ ] **OVE-1..3:** noise-filtered unusual options buying (abnormal volume, block size,
  short-dated OTM premium, no event, clustering) and DIX-direction off-exchange flow;
  pre-register; walk-forward.

## Running

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
