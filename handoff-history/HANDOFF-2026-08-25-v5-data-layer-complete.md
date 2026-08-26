# HANDOFF — state for the next session

Written 2026-08-25 ~14:15 CDT. Protocol: `CLAUDE.md`.
Previous handoff (the PIT universe build itself):
`handoff-history/HANDOFF-2026-08-24-pit-universe-shipped.md`.

## The one-paragraph state

**The v5 DATA LAYER is COMPLETE and validated** — one day after the PIT
universe froze, everything the freeze/dataset/training campaign needs sits
in `nn_meta/data_cache_v5/` (~10 GB): 500 option day-frames (456 roots),
derived complete universe listing (5.21M contracts) + per-contract daily
bars, underlying daily+15m for all 453 members, and surface features whose
option-window NaN rates (5.0–7.1%, SPY 0%) match v31's benchmark exactly.
Next: the Batch campaign (user decision 2026-08-25: freeze + dataset build
+ assemble + training ALL on GCP on-demand Batch, not the box). V118 was
live-verified on the server today after the user questioned it (it IS
running; see below). Cache backup to GCS is live; migration to the user's
Google Drive (they have Google One) is DEFERRED until the Batch campaign.

## What landed today (all pushed)

1. **Backup**: `scripts/backup_caches.sh` + weekly systemd timer
   (`healys-cache-backup.timer`, NOT yet sudo-installed — user has the
   one-liner). Initial 10 GiB push verified in
   `gs://healys-backtester/backup/homebox/`. data_cache_v5 added to the
   set; a re-sync will pick it up.
2. **v5 flat-files**: `scripts/run_flatfiles_v5.sh` (autosized workers) —
   500 day-frames / 4.9 GB in ~3 h; coverage verified against the
   universe_daily trading-day set (all 499 + 2026-08-24).
3. **v5 cache split**: `DATA_CACHE=data_cache_v5` under `NN_META_POOL=v5`
   (sharing data_cache_v3 would have overwritten v31's frozen inputs).
4. **Symbology fixes** (`FETCH_ALIASES = {"BRKB": "BRK.B"}`, fetch-only,
   never rekeys): applied to underlying daily, 15m, AND the contracts
   reference crawl (underlying_ticker=BRKB returns 0; BRK.B returns the
   O:BRKB… chain). BRKB now fully covered.
5. **Universe/bars derivation**: `v3.derive_contracts --cache
   nn_meta/data_cache_v5` (the v31 recipe) — the crawled, moneyness-
   filtered universe.parquet was the WRONG semantics for chain selection
   and was replaced by the derived complete listing. contracts.parquet
   (REST crawl) remains as a validation artifact only.
6. **Coverage audit CLEAN**: all 6,311 member-months have 15m bars; dead
   members' bars end at their death dates (X 2025-06-17, WBA 2025-08-27…).
7. **V118 verification** (user thought it wasn't deployed): server on
   main+clean, bundle `model_final_v4/` = 40 gbt seeds + magnitude heads,
   crontab correct. The 8:32 AM alerts on Monday-close bars are the RTH
   gate working as built: the 19:45 UTC bar completes AT the close, the
   20:00 pass exits at `is_rth`, so close-bar signals deliver at the next
   open (precedent: the 2026-08-17 KO alert, same 13:33 UTC pattern).
   P(win) 43% alerts with EV ≥ +5% are V118's signature — the old
   filter/0.5 policy could not emit them. 5 alerts day one ≈ the looser
   EV gate, watch the digest hit-rates from ~Wednesday.

## Next moves (the Batch campaign)

- Design the v5 run: freeze (10 families × 453 names) + dataset build +
  assemble (`--membership` default ON) + training, all as Batch jobs —
  rebuild image + pin `IMAGE_TAG` first; ship data_cache_v5 (~10 GB) to
  the bucket as job input. Open design questions: extend WINDOW_END /
  EXPIRY_MAX beyond the v31-era 2026-07-02/2026-08-15 constants (they're
  static, decide + document); Batch shard shape for the freeze.
- Drive backup migration (user has Google One): rclone OAuth (user step) →
  re-point backup_caches.sh → verify full copy → THEN delete GCS
  backup/homebox with explicit user go-ahead. See memory
  `backup-drive-migration-plan`.
- Monthly PIT upkeep (crawl+freeze on the box) still needs its timer.

## Standing warnings (delta from yesterday)

- Background harness tasks kept getting killed today (three times, no
  OOM); long local jobs should run detached (`setsid nohup … &`) with a
  log file, like `run_flatfiles_v5.sh` does.
- Known v5 limitation (accepted, mirrors v31): renamed listings XYZ/FISV/
  DRAM have no pre-rename-era CONTRACTS (old roots not crawled; strike-
  basis risk if a rename had a conversion ratio). Underlying bars are
  complete via aliased fetch.
- The surface's headline NaN looks scary (~22%) but is the pre-entitlement
  warmup (2024-04→08); in the option window it is 5.0–7.1% — do not "fix".
- `v3/data/universe_daily/` + `data_cache_v5/` are irreplaceable once the
  entitlement rolls; they're in the backup set.
- Everything else: see the 2026-08-24 handoffs (Docker bakes repo; never
  report cloud state from memory; deploy via git pull; don't delete the
  gs:// archive; DD-brake gap in v4_scan sizing).
