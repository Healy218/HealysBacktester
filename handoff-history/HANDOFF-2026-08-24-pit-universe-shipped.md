# HANDOFF — state for the next session

Written 2026-08-24 ~late evening CDT. Protocol: `CLAUDE.md`.
Previous handoff (V118 going live, wave-2 phase entry, the day's seven GCP
verdicts): `handoff-history/HANDOFF-2026-08-24-wave2-entry.md`.

## The one-paragraph state

**The PIT universe shipped end-to-end today — v5 is unblocked.** All four
spec steps (`docs/specs/PIT_UNIVERSE_SPEC.md`, now stamped BUILT) landed:
stage-B module + 17 tests, home-box day_aggs crawler, 496-day backfill,
21 frozen monthlies (2024-11→2026-07, `v3/artifacts/universe_pit/`),
and `--membership` wired into `build_meta_dataset` + `walkforward_meta`
(default ON for v5, which now derives 453 UNDERLYINGS from the frozen
artifacts). Everything committed and pushed; suite 508 green in ~13 s.
Otherwise the world is as the previous handoff left it: [v4] V118 live
with real alerts on Hetzner, spx0 parked pending the USER DECISION
(lever-5 data vs park), vol track at stage 3's doorstep.

## What landed (commits `9b212df` → docs)

1. `nn_meta/universe_pit.py` — pure stage B: 63-day median option
   $-volume, ≥50 active days, hysteresis 270/330, write-once monthly
   freeze, fail-closed gates (delisting canary, loud parse), CLI driver
   (`python -m nn_meta.universe_pit --through YYYY-MM --canary ... --freeze`).
2. `scripts/build_universe_daily.py` — resumable per-day crawler.
   **Probed: the rolling 2y entitlement starts 2024-08-26 exactly**;
   ~4.6k roots/day; 42 MB of daily rows in `v3/data/universe_daily/`
   (gitignored — the ONLY copy of days that have rolled off entitlement).
3. Backfill + freeze: ~300 members/month, ~10/mo churn each way; spec
   defaults held, no retune. Canaries X/SWTX/WBA pass (MRO/JNPR/HES etc.
   died in-window but were never top-270 liquid). **Renames discovered:
   FI→FISV (2025-11-11), BITF→DRAM (2026-04-07)** — added to
   `TICKER_ALIASES`, stints stitch gap-free.
4. Stage C: v5 `UNDERLYINGS` = union of frozen monthlies;
   `membership_mask`/`members_asof` filter (symbol, month) rows.
   Fixed: a freeze is usable during month M iff `available_at` falls
   within M (first-calendar-day compare zeroed months starting on a
   weekend — Dec 2024 had 0 members before the fix).

## Next moves (in priority order per TODO)

- **v5 generation is runnable**: `NN_META_POOL=v5` end-to-end (download →
  freeze → dataset → walk-forward with PBO + deflated Sharpe already
  wired). It's a big Batch job — rebuild + pin `IMAGE_TAG` first; note
  453 names ≈ 3.7× the v31 crawl/build cost.
- **Monthly PIT upkeep**: crawl + freeze must run monthly on the HOME box
  (entitlement rolls forward — crawl promptly). Fold into the same
  systemd-timer automation as the FA monthly freeze (TODO block 3).
- Vol track stage 3 (TODO block 4) and the spx0 USER DECISION are
  unchanged from the previous handoff.
- Monday watch still stands: first real [v4] alerts, first populated
  watchlist digest 20:10 UTC.

## Standing warnings (unchanged unless noted)

- Docker image BAKES the repo → rebuild + pin `IMAGE_TAG` after every
  code change; never report cloud state from memory.
- `NN_META_POOL=v31` for v4/spx0 work; `v5` only for the new generation.
- Deploy by `git pull`, never scp; server crontab edits staged to a file.
- Do NOT delete `gs://healys-backtester/out/archive-2026-08-19-stale-cache/`.
- NEW: treat `v3/data/universe_daily/` as precious (back it up with the
  other caches) — pre-2024-08-26 daily rows can never be re-downloaded,
  and each passing day rolls another day off the entitlement's front.
- Live DD-brake enforcement still missing in v4_scan sizing (TODO block 5
  remainder; moot for V118's `dd_brake=None`).
- Ultrareview retry: 2 of 3 free remain; branch has only had local review.
