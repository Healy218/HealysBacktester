# Handoff — October 11, 2026 — UV1–UV3 intraday timing tests (all FAIL); user reviews them Monday

## Focus

Start of the "user's market view" phase. Instead of the planned interview, the user proposed simple
SPY/QQQ timing rules, and three escalating, pre-registered tests ran the same day (UV1 → UV2 → UV3).
All failed. The user doubts the results ("there is no way we ran every possible move ... in 20
minutes just for you to say nope") and will **review everything on Monday 2026-10-12**. First job
next session: support that review. Show the trades, the code and the method, and fix anything
they find. Do not defend the verdicts; check them with the user.

## What ran (details and tables in [EXPERIMENTS](docs/EXPERIMENTS.md))

| Test | Rule | Verdict |
|---|---|---|
| UV1 ([spec](docs/specs/UV1_MIDDAY_FADE_PREREG_20261011.json)) | 10:30 CT: fade a < 1% move from the open (or the last 15-min bar) with first-OTM 0DTE options or stock, hold 2 h, by weekday; 48 variants | FAIL, no positive cell; options −16% to −19%/trade; no midday reversal (gross ≈ −1 bp) |
| UV2 ([spec](docs/specs/UV2_HOUR_SCAN_PREREG_20261011.json)) | Same rule, 1-hour hold, every entry minute 09:45–14:59 ET, fade and follow; 30,240 cells | FAIL: both family-wise outliers lost in 2026 |
| UV3 ([spec](docs/specs/UV3_FULL_GRID_PREREG_20261011.json)) | Move buckets ±0.25–2.5% × call/put (stock buys) × stops 5–50% × targets 10–200% × holds 30–240 min × entries every 5 min; ~2.4M option cells | FAIL: weak stock intraday momentum (count p 0.005, no single cell passes); 4 option candidates (one QQQ put 20%-target trade set, 29/30 wins) lost −24% to −27% in 2026 |

Method in all three: frozen spec committed before the run, single run, option cost = mid × 1.05 to
buy and mid × 0.95 to sell (user's rule), mid = minute trade VWAP (Alpaca has no historical option
quotes), stock 1 bp per side, dev = 2016–2025 stock / 2024-01-18–2025 options, 2026 confirmation only
for candidates. UV2/UV3 use a 200-permutation family-wise null (shuffle days' signals, keep returns).

## Review aids for the user

- UV1 every trade: `nn_meta/validation/uv1-midday-fade-20261011-r0/trades_for_review.csv` (12,113 rows;
  e.g. 2025-09-05 SPY250905C00647000 bought ≈ $0.87 at 10:30 CT, ≈ $0.35 at 12:30 CT, −63%).
- UV2/UV3 cell tables: `nn_meta/validation/uv2-hour-scan-20261011-r0/cells_*.parquet`,
  `nn_meta/validation/uv3-full-grid-20261011-r0/cells_{S,O}.parquet` (UV3 options: 2.4M rows; all n ≥ 30).
- Code checks done: UV2 reproduces every UV1 trade exactly at UV1's clock; UV3 reproduces UV2's
  no-stop 1-hour returns; UV3 stop/target exits toy-checked (`run_uv3_full_grid.py check`).
- Raw data: `nn_meta/data_cache_uv1/` (SIP 1-min SPY/QQQ 2016–2026-10-09; 0DTE contracts and full-day
  1-min option bars from 2024-01-18; 364 MB).

## Known limits to raise honestly if asked

- Option history is only about two years (Alpaca starts 2024-01-18); weekday × bucket cells are thin.
- Trade VWAP stands in for the midpoint; stop/target fills use the next traded minute's VWAP.
- UV3 confirmation applied the n ≥ 30 floor to 2026 t-stats (t shows NaN); the negative 2026 means
  decide the verdict regardless.
- The only structure found is stock intraday momentum (buy after a modest up morning, avoid buying
  after down mornings). It is too weak for options, and no single cell passes; new data would be needed.

## Next actions

1. Monday: walk through the user's review; fix any defect, rerun only what it affects, record it.
2. Then the planned interview (setups the user won on), as in the [previous handoff](handoff-history/HANDOFF-2026-10-09-v9-closed.md).
3. Still open from Oct 9: Alpha Vantage key rotation, and whether to disable `healys-v9-alphavantage.timer`.

## Running (not re-verified this session)

UV1 forward log `healys-uv1-forward.timer` (new 2026-10-11; first run Mon 2026-10-12 14:05 ET; verified on 2026-10-09
against the UV1 trades) → `nn_meta/data_cache_uv1/forward/uv1_forward.csv`.
V8 H1 paper test ("stonks bot 2"), OI recorder and Alpha Vantage timers as in [TODO](TODO.md#running).
Constraints: stage only your own hunks (other V6/V7 work is dirty in the tree; EXPERIMENTS entries were
appended via the index); memory caps on big jobs.
