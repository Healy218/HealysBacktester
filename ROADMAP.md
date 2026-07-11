# Roadmap — the plan for the plans

One page. Each phase gates the next; specs hold the detail.
Reconciled 2026-07-11 to reflect what actually shipped.

```
DONE ─► v2.2 ROBUST ─► live server + collectors ─► v3-small ROBUST & LIVE
                                                          │
NOW ──────────────────────────────────────────────────── ▼
   weekend prep ─► big run (v3-at-scale) ─► FA ranker ─► v4 (loop closes)
```

## ✅ Done
- **v2.2 walk-forward: ROBUST** (`nn_meta/reports/meta_report.md`). 4-strategy
  pool, 56 symbols, ~2y options window.
- **Live alert server** (Hetzner, [[hetzner-server]]): 15-min scanner →
  Telegram, hourly FA Stage-0 collectors (Reddit incl. comment stream,
  StockTwits, EDGAR, news) archiving to append-only parquet.
- **v3-small: ROBUST & LIVE (2026-07-11)**. 7-strategy pool (added TV-derived
  supertrend / tv_rating / squeeze), rank/label_excess/32x16. Beats baseline
  3/3, B&H 2/3; ex-top3 +108%/+111% folds 2-3 — outlier dependence gone vs
  v2.2. Swapped onto the scanner via `NN_META_POOL=v3`. Still the **56-symbol
  / ~2y options** data regime.
- **v3 foundation data**: 289-symbol bootstrap universe + 287M-bar 1m
  underlying crawl (2017→now, `v3/data/`), TV indicator library + Technical
  Ratings, all committed.

## ▶ NOW — weekend prep (gates the big run)
Order matters; each answers a question the big run depends on.

1. **Probe Massive flat-files depth.** REST options history caps at ~2y
   (`[[data-plan-limits]]`, 403s pre-mid-2024). `.env` has untested
   `MASSIVE_FLAT_FILES_*` S3 creds — the flat-files product may reach further.
   **This answers the scope question**: can options *labels* go past 2y, or is
   deep history underlying-only? Nothing else is decidable until this is known.
2. **GBT baseline + feature importances.** Standing rule: new complexity must
   beat the boring baseline before it ships — never yet run. LightGBM on the
   existing 344k-row v3 dataset (seconds on CPU): (a) does the 40-model NN
   actually beat a tree, (b) which strategies/features earn their place — so
   the big run is pruned, not bloated.

## ⏭ Big run — v3-at-scale
Scope decided by prep #1 (depth) and #2 (which features/strategies survive):
- **Path A** — options meta-labeling at 200+ symbols, ~2y labels (feasible now).
- **Path B** — deep-history (2017→) signal research on underlying/equity
  outcomes or a sequence model, if flat-files unlock depth or we accept
  non-options labels.
Universe is still survivorship-biased (present-day list); true point-in-time
selection with annual reconstitution stays TODO pending a constituents source.
**Exit:** at-scale walk-forward verdict + per-regime report.

## ⏭ FA — ticker discovery (`FA_SPEC.md`)
Stage-0 collectors live. Remaining: entity resolution → velocity z-scores →
composite ranker → frozen monthly Top-10 → forward-return tracker →
graduation into the training universe. Two queued, now-unblocked pieces:
daily WSB-trending Telegram digest, and exit/roll alerts on the live scanner.
**Exit:** ≥3 monthly top-10 artifacts frozen and tracking forward returns.

## ⏭ v4 — the loop closes
FA graduation feeds the training universe; retrain on the expanded set;
discovery quality judged by realized forward returns, not vibes.

---
**Standing rules across phases**
- Point-in-time everything; frozen artifacts; no retroactive edits.
- Checkpoint every long stage (spot-safe by construction).
- Evaluate portfolio-level, out-of-fold, with costs, ex-outliers.
- New complexity must beat the boring baseline (GBT, buy-and-hold basket)
  before it ships.

_(Native-Linux rebuild of the Windows box: out of scope — side project, later.)_
