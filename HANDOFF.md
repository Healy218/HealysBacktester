# Handoff — October 7, 2026 — V8.0-pit done; V8.0-data next

## Where things stand

- **V8 is the selected work** ([spec](docs/specs/V8_DESIGN_20261007.md), [TODO](TODO.md)):
  prove an edge on liquid stocks/ETFs under realistic fills before any model or
  options. Stages 0–1 are authorized; later stages need the user's go-ahead.
- **No paid data.** V8 reads V7's raw inputs in place on MRHA and uses Alpaca's
  free tier for gaps (XLB, XLC, XLRE). Paths: [CURRENT_STATE](docs/CURRENT_STATE.md)
  "V8 data sources". Never unpack `v7/data/*.tar.zst`; write nothing to MRHA.

## This session: V8.0-pit (passed)

- `scripts/build_v8_universe_pit.py` reduced all 1,430 sealed day-aggregate files
  (2021-01-04 → 2026-09-14) with the unchanged `universe_pit` code and parameters
  into `nn_meta/validation/v8-pit-20261007-r0/` (117 MB): 65 monthlies, 2021-04 →
  2026-08. Every V3 member-row on 2024-11 → 2026-07 had identical rank/score
  before hygiene; seven delisting canaries pass; all calendar gaps are holidays.
- Found and fixed **V8-locally**: 11 OPRA test roots that were members in
  2021-12 → 2022-06, and ticker renames that dropped names for ~3 months (FB→META,
  VIAC→PARA→PSKY, GOLD→B, DISCA→WBD, DWAC→DJT, …). The committed V3 artifacts
  have the same GOLD→B gap (2025-05/07); left untouched (write-once, V5 inputs).
- `scripts/freeze_v8_pool.py` resolved SEC SIC for all members (dead tickers via
  EDGAR full-text search on XBRL filename prefixes plus 10 verified manual CIKs)
  and froze [V8_POOL_PIT2021_20261007.json](docs/specs/V8_POOL_PIT2021_20261007.json):
  66–109 tech names per month, 162 distinct (incl. TWTR, XLNX, SPLK, VMW, ATVI), plus
  17 ETFs. It supersedes `V8_POOL_20261007.json`.
- Evidence: [EXPERIMENTS](docs/EXPERIMENTS.md) "V8.0-pit"; decision:
  [DECISIONS](docs/DECISIONS.md) "V8 PIT root hygiene". Tests:
  `tests/test_v8_universe_pit.py` (with `test_universe_pit.py`, 22 pass).

## Status at session end

No jobs running. V6 paper services remain paused by user choice; one V6 paper
position (TMUS) is open. ROADMAP has no V8 workstream section yet (V8 lives in the
spec, TODO and DECISIONS); add one if the user wants V8 tracked there.

## Next action

**V8.0-data:** 1-minute stock bars for the new pool (162 tech + 17 ETFs, 2021+)
from the V7 payload store (`*/stock_1m/{raw,all}/<SYM>/<YEAR>/…/bars.parquet` via
`files.sqlite3`), XLB/XLC/XLRE from Alpaca free tier, coverage report per symbol
and day. The new pool includes dead and 2021-era names that the V7 bar store
(624 securities) may lack; list those first. Then -spreads, -liquidity, -fills,
-contract, and stage-1 pre-registration.

Constraints: stream per symbol/day under `systemd-run --user --scope -p
MemoryMax=…`; keep the local footprint to a few GB; stage only your own hunks
(other dirty V6/V7 work in the tree, including in DECISIONS/EXPERIMENTS, is not
yours).

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-v8-pit.md).
