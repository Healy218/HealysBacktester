# Handoff — October 7, 2026 — V8 selected; stage 0 starts with the PIT rebuild

## Where things stand

- **V8 is the selected work** ([spec](docs/specs/V8_DESIGN_20261007.md), [TODO](TODO.md)).
  Prove an edge on liquid stocks/ETFs under realistic fills before any model or
  options. Universe: mostly tech plus SPDR sector and broad ETFs. Stages 0–1 are
  authorized; later stages need the user's go-ahead.
- **Why:** every earlier generation's edge came from an evaluation flaw (v3 leak,
  v4/v5 gate changes, v6 midpoint fills on illiquid options, ETFE fill/expiry
  artifacts), and direct tests found no edge. All October 7 evidence is in
  [EXPERIMENTS](docs/EXPERIMENTS.md); decisions in [DECISIONS](docs/DECISIONS.md).
- **No paid data.** Massive and Alpaca paid plans are cancelled. V8 reads V7's raw
  inputs in place on MRHA (option day aggregates 2021-01 → 2026-09-14, 1-minute
  bars for 624 securities from 2021, option NBBO quote windows from 2022-03) and
  uses Alpaca's free tier for gaps (XLB, XLC, XLRE). Paths and formats are in
  [CURRENT_STATE](docs/CURRENT_STATE.md) ("V8 data sources"). Do not unpack the
  `v7/data/*.tar.zst` shards; V8 needs none of them.
- **Pool:** frozen for 2024-11 → 2026-07 in
  [V8_POOL_20261007.json](docs/specs/V8_POOL_20261007.json): 73–107 tech names per
  month by SEC SIC rule plus 9 declared tech-adjacent platforms, and 17 ETFs. It is
  re-frozen from ~2021-04 after the PIT rebuild.

## Status at session end

No jobs running. V6 paper services remain paused by user choice (the scanner fails
each run on stale data, as expected); one V6 paper position (TMUS) is open.
Research roots from today (`v6-fillcost-20261007-r0`, `v8-stage0-20261007-r0`)
are under `nn_meta/validation/` (gitignored).

## Next action

**V8.0-pit:** rebuild the monthly PIT universe from the 2021+ option day aggregates
with the existing `nn_meta/universe_pit.py` and parameters, into a V8 root. Check
the overlap months against `v3/artifacts/universe_pit/`, pass the delisting
canaries, then re-freeze the pool from ~2021-04. Then V8.0-data, -spreads,
-liquidity, -fills, -contract, and stage-1 pre-registration.

Constraints: stream per symbol/day under `systemd-run --user --scope -p MemoryMax=…`
(a full in-memory load crashed this box); keep the local footprint to a few GB;
write nothing to MRHA; stage only your own hunks when committing (other dirty
V6/V7 work in the tree is not yours).

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-v8-stage0.md).
