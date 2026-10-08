# Handoff — October 8, 2026 — V8.0-data, -spreads, -liquidity done; V8.0-fills next

## Where things stand

- **V8 is the selected work** ([ROADMAP](ROADMAP.md#v8--edge-first-on-liquid-stocks-and-etfs),
  [spec](docs/specs/V8_DESIGN_20261007.md), [TODO](TODO.md)): prove an edge on liquid
  stocks/ETFs under realistic fills before any model or options. Stages 0–1 are
  authorized; later stages need the user's go-ahead.
- **User decisions (October 8):** delisted names stay in the historical test while
  they were members (survivorship-free); live/paper only see current members. The
  V7 bar archive (624 securities) is a data source, not V8's universe.
- **No paid data.** V7 raw inputs read in place on MRHA (never unpacked, never
  written) plus Alpaca's free tier. Paths: [CURRENT_STATE](docs/CURRENT_STATE.md)
  "V8 data sources".

## Done so far (V8.0)

- **V8.0-pit** (Oct 7): 65 PIT monthlies 2021-04 → 2026-08; pool
  [V8_POOL_PIT2021_20261007.json](docs/specs/V8_POOL_PIT2021_20261007.json), 162 tech
  names (incl. delisted) + 17 ETFs.
- **V8.0-data** (Oct 8): `scripts/build_v8_bars.py` →
  `nn_meta/validation/v8-data-20261008-r0/` (190 MB): hourly (09:30-anchored) and
  daily regular-session bars, raw + adjusted, all 179 symbols. Bars follow the PIT
  identity (META←FB, XYZ←SQ, …) plus overrides for reused tickers (COHR←IIVI,
  WOLF←CREE, SPCX/FIG cut at listing). Coverage: 127,125 complete, 83 partial
  (upstream feed gaps, same in Alpaca), 3 missing (2022-03-08), 138 post-delisting.
  WOLF 2025-09-29 reorganization is a series break in `events.json`.
  [Evidence](docs/EXPERIMENTS.md). Tests: `tests/test_v8_bars.py`.

## Status at session end

No jobs running. V6 paper services paused by user choice; one V6 paper position
(TMUS) open.

## Next action

**V8.0-fills:** stock fill model: fill at mid ± measured half-spread (table by price
bucket × time of day × year from `v8-spreads-stock-20261008-r0`, times a per-name
factor), plus slippage allowance and fees; option fills mid ± k × half-spread (k = 1.0
primary, 0.5 sensitivity) for stage 3. Unit tests on hand cases. Then -contract and
stage-1 pre-registration. V8.0-liquidity is done (user-approved rule frozen in
[V8_LIQUIDITY_20261008.json](docs/specs/V8_LIQUIDITY_20261008.json)).

Also done October 8: V8.0-spreads ([evidence](docs/EXPERIMENTS.md)); parallel
builders (`nn_meta/v8_parallel.py`, user preference: worker pools and vectorized
code by default).

Constraints: stream under `systemd-run --user --scope -p MemoryMax=…`; keep the
local footprint to a few GB; stage only your own hunks (other dirty V6/V7 work,
including in DECISIONS/EXPERIMENTS, is not yours).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-before-v8-data.md).
