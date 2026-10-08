# Handoff — October 8, 2026 (night) — OEE-2 FAIL; OVE recorder running

## Where things stand

- **V9** ([plan](docs/specs/V9_OPTIONS_EXPERTS_PLAN_20261008.md), [TODO](TODO.md),
  [ROADMAP](ROADMAP.md#v9--options-experts-oee-and-ove)).
- **OEE-0 done:** earnings event table, 1,354 events / 1,265 admitted
  (`nn_meta/validation/v9-oee0-20261008-r0/`).
- **OEE-1 frozen** with the user's approval:
  [V9_OEE1_PREREG_20261008.json](docs/specs/V9_OEE1_PREREG_20261008.json). After the
  freeze the user raised the post-pass per-day premium cap from 10% to 25%
  ([DECISIONS](docs/DECISIONS.md)); that changes sizing only, not the pass rules.
- **OEE-2 FAIL, all 8 variants** ([EXPERIMENTS](docs/EXPERIMENTS.md), last entry).
  - Directional 0.5-delta options lost 9–14% per trade, and the hit rates were 32–34%.
  - The long straddles were near zero to slightly negative.
  - The short iron fly lost 58% of max loss; costs alone took 53 points.
  - The IV run-up idea is not supported: the move relative to the implied move was
    0.99 / 0.97 / 1.00 across the run-up terciles.
  - No 2026 confirmation was run.
  - The first run was voided: it priced expiry-day exits at the last trade instead of
    the pre-registered intrinsic value (`*_INVALID_expiry_pricing.*`; fix 4dc8701).
- **OEE-H4 FAIL, 13 OTM variants** (the user's thesis: OTM strikes near the post-move
  price; prereg [V9_OEE_H4_PREREG_20261008.json](docs/specs/V9_OEE_H4_PREREG_20261008.json)).
  Means rise the further and cheaper OTM (20% strangle +61%, 10% legs ≤ 0.5% of spot
  +108%), but t ≤ 1.5. A few real shocks carry them (SMCI Jan 2024, SNPS/ORCL Sep 2025).
  Without each variant's top 5 trades, all are −17% to −35%.
- **OVE-0 done:** `healys-v9-oi-recorder.timer` snapshots Alpaca open interest twice
  each weekday → `nn_meta/data_cache_v9/open_interest/`.

## Running now

- V8 H1 paper test, "stonks bot 2" (PA3U9D8Q8GQX): first runs 2026-10-09 09:45 / 10:31 /
  16:20 ET. `./venv/bin/python scripts/run_v8_h1_paper.py status`.
- OI recorder: `journalctl --user -u healys-v9-oi-recorder` (first run 2026-10-08 19:09 ET).

## Next action (user's call)

Both OEE pre-registrations (ATM and OTM) are spent; do not re-tune them on these results. Options:
1. **OVE-1:** flow and dark-pool tables (coverage only), using OPRA daily aggregates in
   the V8 chains (volume, trades, premium dollars) plus the FINRA off-exchange volume
   history. Then pre-register OVE-2.
2. A new, separately pre-registered OEE idea that the OEE-2 numbers did not already
   test, for example holding past the reaction day (H1 drift with short-dated calls).
   It needs its own sign-off and must not reuse the failed variants.
3. Watch the H1 paper fills: real option spreads would replace the bucket medians.

Constraints: memory caps on big jobs; stage only your own hunks (other dirty V6/V7
work in the tree, including `docs/DECISIONS.md` and `docs/EXPERIMENTS.md`, is not
yours); the 2026 holdout has been used once (H1 stock).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-oee1-draft.md).
