# Handoff — October 8, 2026 (evening) — OEE-0 and OVE-0 done; OEE-1 awaiting sign-off

## Where things stand

- **V9 is the selected work** ([plan](docs/specs/V9_OPTIONS_EXPERTS_PLAN_20261008.md),
  [TODO](TODO.md), [ROADMAP](ROADMAP.md#v9--options-experts-oee-and-ove)).
- **OEE-0 done** (coverage only): `nn_meta/v9_oee.py`, `scripts/build_v9_oee_events.py`
  → `nn_meta/validation/v9-oee0-20261008-r0/` (about 11 s). 1,354 Item 2.02 8-Ks by pool
  tech names, 1,330 usable; 1,265 pass the draft's liquidity admission (dev 1,007,
  2026 confirmation 258). Per event: entry/reaction days, front-expiry ATM straddle and
  0.5-delta call/put before and after, implied move, fixed-expiry ATM IV E-5..E+1
  (run-up), skew, realized move and gap. Details and known gaps in
  [CURRENT_STATE](docs/CURRENT_STATE.md#v9-plan-october-8).
- **OVE-0 done:** Alpaca's free tier gives contract open interest (with its as-of date,
  lagging about two trading days), daily option bars with volume and trade counts, and
  indicative snapshots. Recorder `scripts/record_v9_open_interest.py`, timer
  `healys-v9-oi-recorder.timer` installed and enabled (Mon–Fri 08:00 / 18:00 ET) →
  `nn_meta/data_cache_v9/open_interest/`. First run 2026-10-08 19:09 ET: 138,784
  contracts, 126/126 underlyings.
- **OEE-1 drafted, not frozen:**
  [V9_OEE1_PREREG_DRAFT_20261008.json](docs/specs/V9_OEE1_PREREG_DRAFT_20261008.json).
  Eight variants: H1a–d direction (combined / SUE / momentum / skew → 0.5-delta call or
  put), H2a–b IV run-up (low → long straddle; high → short iron butterfly; the dev
  move-to-implied ratio must decrease across terciles), H3a–b cheap implied move vs own
  history (long straddle). Pass: day-clustered t ≥ 2, Holm across 8, ≥ 4/6 folds, holds
  at 1.5× spread. No outcome analysis has been run.

## Running now

- V8 H1 paper test, "stonks bot 2" (PA3U9D8Q8GQX): first runs 2026-10-09 09:45 / 10:31 /
  16:20 ET. `./venv/bin/python scripts/run_v8_h1_paper.py status`.
- OI recorder (above). Check `journalctl --user -u healys-v9-oi-recorder`.

## Next action

1. **User sign-off on the OEE-1 draft** (or edits). Then rename to
   `V9_OEE1_PREREG_20261008.json` with `approved_by`, commit, and implement OEE-2:
   features (SUE via `v8_event_signals.sue_table`, revenue acceleration from XBRL facts,
   momentum, skew), wing prices for H2b (needs a chain pass over the OEE-0 events), the
   cost model from `v8-spreads-option-20261008-r0/model.json`, day-clustered t-stats, one
   dev run, then the 2026 confirmation for passing variants only.
2. Optional data fix: alias old root SQ → XYZ in the V8 chain build (11 events).
3. After the first H1 earnings wave: compare H1 paper call fills with decision quotes.

Constraints: memory caps on big jobs; stage only your own hunks (other dirty V6/V7
work in the tree is not yours); the 2026 holdout was used once (H1 stock).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-v9-planned.md).
