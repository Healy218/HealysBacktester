# Roadmap — the plan for the plans

One page. Each phase gates the next; specs hold the detail.
Reconciled 2026-07-11 to reflect what actually shipped.

```
DONE ─► v2.2 ROBUST ─► live server + collectors ─► v3-small ROBUST & LIVE
                                                          │
                                        big run (v3.1-at-scale, done, not a clear win)
                                                          │
NOW ──────────────────────────────────────────────────── ▼
        v4 causal validation (smoke test ─► ablation ─► gates) ─► FA ranker ─► loop closes
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

## ✅ Big run — v3.1-at-scale (DONE 2026-07-21, Path A)
**Decided 2026-07-11: Path A.** 120 symbols (by $volume, all v2 included),
pruned 5-pool (rsi/tv_rating/macd/squeeze/ma), flat-files ingestion. Confirmed:
flat-files reads are entitlement-gated to a rolling ~2y (cutoff ~Sept 2024) —
NOT the 9y the underlying crawl has. So option **labels** run ~2024-09→now;
the 9y underlying feeds longer-window features only. Universe is
survivorship-biased (present-day list); point-in-time selection stays TODO.
**Verdict: technically ROBUST but not production-ready.** Walk-forward beats
baseline 2/3 folds, B&H 2/3 (`nn_meta/reports_v31/meta_report.md`), one-shot
test looks flashy (+499% vs baseline +280%) — but fold-level ex-top3 checks
show the wins are outlier-concentrated (fold 2's +1136% collapses to +18%
without its single best trade, a 31x overnight TQQQ position) in a way
**v3-small's walk-forward is not** (ex-top3 barely moves vs its own headline
in any fold). **Do not swap the live scanner (still `NN_META_POOL=v3`) over
to v3.1 as-is.** `meta_dataset.parquet` + `baseline_spec.json` committed to
main (needed by v4, see below) — the rest of `artifacts_v31/` stays
out-of-git (regenerable / too large).

## ⏭ NEXT after this run — bigger bucket, longer span (user intent 2026-07-11)
Once this v3-at-scale trains, expand the universe AND the history. Requires a
**paid Massive/Polygon historical-options entitlement** (the only blocker —
proven, not a code gap). Then it's purely data+compute: `v3/flatfiles.py`
already handles the full 2017→2026 window, so a wider `--universe` + earlier
`--start` re-download feeds the same freeze/train/walk-forward chain. Path B
(9y underlying-only model) remains an alternative if the entitlement isn't
bought.

## ⏭ FA — ticker discovery (`FA_SPEC.md`)
Stage-0 collectors live. Remaining: entity resolution → velocity z-scores →
composite ranker → frozen monthly Top-10 → forward-return tracker →
graduation into the training universe. Two queued, now-unblocked pieces:
daily WSB-trending Telegram digest, and exit/roll alerts on the live scanner.
**Exit:** ≥3 monthly top-10 artifacts frozen and tracking forward returns.

## ▶ NOW — v4 causal validation (`codex/v4-causal-validation` branch, `V4_OUTLINE.md`)
Started 2026-07-20, unblocked 2026-07-21 once v3.1's `meta_dataset.parquet` +
`baseline_spec.json` landed on main. Purpose: v3.1's walk-forward "ROBUST"
verdict above is outlier-fragile and possibly leakage-inflated (`prem_spot`
is a suspected pre-decision-unsafe feature); v4 fixes the causal contract
(feature timing, exit-time purging, embargoes, model/threshold selection
**nested inside each fold** instead of reusing one globally-chosen config)
and re-evaluates the same v3.1 data before trusting any of it as evidence of
a real edge. Gate: `main` stays the operational v3 line until v4's own
"first implementation gate" passes (`V4_OUTLINE.md`) — no premature swap.
**Before the full nested-fold ablation (compute-heavy, likely hours):
smoke-test the corrected pipeline on a tiny 10-symbol/~1y subset first** —
see `V4_SMOKE_TEST.md`. Runs on the MacBook; the full `nn_meta/data_cache_v3`
raw option-bar cache (5.6GB, Windows/WSL-only) is NOT needed — `v4_evaluate.py`
and `v4_preflight.py` only ever read the already-committed
`meta_dataset.parquet` + `baseline_spec.json`.

## ⏭ v4 stage 6 — FA-to-universe loop closes
Once v4's causal gates pass: FA graduation feeds the training universe;
retrain on the expanded set; discovery quality judged by realized forward
returns, not vibes. (Subsumed into `V4_OUTLINE.md` stage 6 — no longer a
separate future phase.)

---
**Standing rules across phases**
- Point-in-time everything; frozen artifacts; no retroactive edits.
- Checkpoint every long stage (spot-safe by construction).
- Evaluate portfolio-level, out-of-fold, with costs, ex-outliers.
- New complexity must beat the boring baseline (GBT, buy-and-hold basket)
  before it ships.

_(Native-Linux rebuild of the Windows box: out of scope — side project, later.)_
