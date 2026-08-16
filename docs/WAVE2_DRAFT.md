# DRAFT — apply to ROADMAP.md ⏭ NEXT + TODO.md after the ultra review lands
# (user goals set 2026-08-16 night, via structured Q&A)

## ROADMAP ⏭ NEXT becomes: "Expert panel — wave 2" (week of 2026-08-17)

Prereq: the current phase closes first (Option B ledger re-runs → re-finalize
→ [v4] bundle swap, --paper off).

User-set priorities, in dependency order:

1. **EV-sized v4 expert** — the cheapest new seat, attacks the known
   win-often-win-small inversion. Chain: marks dataset (landing) → train the
   magnitude/EV head (`ev_sizing.py` labels are code-ready) → EV policy joins
   the nested grid → must beat uniform slots through the ledger → deploys as
   a separate labeled seat ([v4ev]), alongside not replacing.
   Compute: small (CPU-hours); local or cloud.

2. **SPX/NDX daily-options trader — NEW expert, user priority #5, ranked
   ahead of vol-regime (stated 2026-08-16 night).** Spec as given:
   - Instruments: SPX + NDX **daily-expiry** options (0/1-DTE class), calls
     AND puts, cash-settled index options.
   - Data: ~2 years of MINUTE data — underlying + options — for both roots;
     train on daily contracts.
   - Trading rules: multiple trades per day allowed; entries AND exits are
     signal-driven (strategy signals close positions, not just expiry);
     **25% max-drawdown gate** (vs the 40% cap elsewhere); no upside cap.
   - Architecture: a NEW pool (working name `spx0`) through the SAME v4
     causal contract — own universe (SPX/SPXW + NDX/NDXP roots), own
     freeze → dataset → train → nested walk-forward → seat on the panel.
     The pipeline is pool-generic already; minute-level options come from
     the flat-files day files (OPRA carries index options).
   - **Stage 0 data audit gates everything** (standing rule): ① confirm
     SPXW/NDXP minute aggs are actually present + within the 2y entitlement
     in the flat files; ② solve the UNDERLYING feed — SPX/NDX index values
     are a separate Massive entitlement from stocks; fallback plan is
     signals computed on SPY/QQQ minute bars (Alpaca, already available)
     with ratio-mapped strikes, decided by the audit, not assumed.
   - Costs modeling matters more here than anywhere (per-contract index
     option fees + spreads on small premiums) — explicit cost scenarios in
     the eval, per the stage-2 accounting contract.

3. **Vol-regime track (track 1)** — after the SPX/NDX trader is underway:
   the first BIG GCP Batch job after the pilot passes: upload v3/data
   (5.4 GB 1m underlying, 2017→) → 9y intraday realized-vol dataset → full
   HAR-RV/GARCH OOS run → one small sequence model that must beat them per
   regime or is dropped. Product: available_at-stamped vol features for
   every expert; a regime-aware seat only if the features prove out.

4. **FA-discovery expert** — turn 6 weeks of archived social/filings history
   into a seat: composite ranker (heuristic weights, documented) → FIRST
   FROZEN monthly Top-10 artifact → forward-return tracker → [fa]-labeled
   digest + the queued WSB daily trending digest cron. Forward-accumulating,
   no heavy compute. Exit metric unchanged: ≥3 frozen monthlies tracking.

5. **Panel cadence architecture (both modes, user decision)**:
   - Every expert gains a **daily top-N watchlist digest** — its N best-
     scored candidates of the day regardless of threshold, clearly labeled
     "watchlist" (flow to browse, not pings).
   - Threshold-gated instant alerts stay as-is (conviction pings).
   - Scoreboard follow-up: EXPERIMENTS tracks watchlist hit-rates so the
     dial between the two modes is data-driven.

Stacked blend (track 4) stays queued behind these (needs their outputs);
RL sizing stays last (doctrine).

## Compute venue policy (user decision)
Heavy runs go to **GCP Batch contingent on the 2-symbol pilot diffing
byte-identical**; the home box keeps small jobs and stays the data-crawl
host (entitlement/keys never leave home). Budget guard $25 already armed.

## TODO.md seed for next phase (when current phase exits)
- [ ] SPX/NDX stage-0 audit: probe flat files for SPXW/NDXP minute aggs +
      entitlement window; decide the underlying feed (index entitlement vs
      SPY/QQQ proxy signals); written findings gate the build
- [ ] `spx0` pool scaffolding: config pool entry, universe/downloader for
      the two roots, 25% DD gate constant, signal-exit execution check
- [ ] Magnitude/EV head training run + grid eval through the ledger
- [ ] [v4ev] seat: EV-ranked scoring path + labeled alerts + paper ledger
- [ ] v3/data → bucket; vol-dataset Batch job spec; HAR/GARCH full OOS run
- [ ] Sequence-vol model vs classical gate (drop if not beaten per regime)
- [ ] fa: composite ranker + frozen monthly Top-10 #1 + tracker + WSB digest cron
- [ ] Watchlist mode: v4_scan --watchlist N + legacy scanner equivalent +
      daily digest crons per expert
- [ ] Scoreboard: per-expert watchlist hit-rate tracking
