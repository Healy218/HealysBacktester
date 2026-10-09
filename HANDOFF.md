# Handoff — October 8, 2026 (late) — V9 tested: 36 variants, none pass

## Where things stand

- **V9** ([plan](docs/specs/V9_OPTIONS_EXPERTS_PLAN_20261008.md), [TODO](TODO.md),
  [ROADMAP](ROADMAP.md#v9--options-experts-oee-and-ove)). Every test was pre-registered,
  approved by the user, run once and recorded in [EXPERIMENTS](docs/EXPERIMENTS.md):
  - **OEE-2:** 8 ATM earnings variants. FAIL. Implied moves were fair on average; the IV
    run-up idea is not supported.
  - **OEE-H4:** 13 OTM variants (the user's thesis). FAIL. The further and cheaper OTM, the
    higher the mean (t ≤ 1.5), but a few real shocks carry it (SMCI Jan 2024, SNPS/ORCL
    Sep 2025).
  - **OEE-J:** 6 FA + TA-pool agreement variants. FAIL. Direction accuracy was 49–50%.
  - **OVE-3:** 9 options-flow and dark-pool variants. FAIL.
    - Buying options after unusual flow lost 10–19%.
    - Pre-earnings flow imbalance called direction 47.9% of the time.
    - Near-miss B1 (high FINRA off-exchange short ratio → long stock 5 days): t 2.48,
      Holm 0.061, but −0.12% vs the equal-weight tech universe, so it is market beta.
- **Data built (reusable):**
  - OEE-0 earnings event table: `v9-oee0-20261008-r0`.
  - OTM leg table: `v9-oee-h4-20261008-r0/legs.parquet`.
  - FA/TA scores: `v9-oee-j-…/scores.parquet`.
  - OVE-1 daily flow table: `v9-ove1-20261008-r0/flow.parquet`.
  - Paths are in [CURRENT_STATE](docs/CURRENT_STATE.md#v9-plan-october-8).
- **User decisions:** per-day premium cap 25% (sizing only); V6 stays retired; no paid data
  without evidence.

## Running now

- V8 H1 paper test, "stonks bot 2" (PA3U9D8Q8GQX), first runs 2026-10-09 09:45 / 10:31 /
  16:20 ET: `./venv/bin/python scripts/run_v8_h1_paper.py status`.
- OI recorder `healys-v9-oi-recorder.timer` (Mon–Fri 08:00 / 18:00 ET) →
  `nn_meta/data_cache_v9/open_interest/`; `journalctl --user -u healys-v9-oi-recorder`.

## Next action

The user wants to keep pursuing earnings direction with **alternative data** (notes and source
survey: [docs/reviews/2026-10-08-v9-findings-and-alt-data.md](docs/reviews/2026-10-08-v9-findings-and-alt-data.md)).
Next is ALT-0 (coverage-only feature table) once approved: analyst actions and consensus are
already in the Benzinga headlines on disk; Alpha Vantage gives consensus history at 25
requests/day.

Earlier options, still open:

All V9 pre-registrations are spent; do not re-tune them on these results. Remaining options:
1. Forward paper observation of one cheap-OTM earnings rule at small fixed size (not a
   validated edge; the only way to learn whether fat-tail payoffs repeat).
2. After a few months of the OI recorder: a new pre-registration on opening-vs-closing open
   interest (data a daily-aggregate backtest cannot see).
3. Review the V8 H1 paper fills after the first earnings wave (real option spreads).

Constraints: memory caps on big jobs; stage only your own hunks (other dirty V6/V7 work,
including `docs/DECISIONS.md` and `docs/EXPERIMENTS.md`, is not yours; this session
committed its own appended entries via the index); the 2026 holdout was used once
(H1 stock).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-oee-done.md).
