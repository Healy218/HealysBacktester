# TODO — current phase

**Phase: Expert panel, wave 2 → generation v6 groundwork** (`ROADMAP.md`).
Re-prioritised 2026-09-05 after the v5 campaign (freeze 75 h/$40 on Batch,
build 29 Aug→4 Sep across three fleet rebuilds + the box, ladder ~1.5 h on
the box). Order of operations agreed 2026-09-05 — work top to bottom:

1. **Monday 2026-09-08 watch (see HANDOFF first actions)** — the first
   session on streamed bars + :01 crons + parallel detection; all prior paper
   records are void as intraday records (EXPERIMENTS 2026-09-05). Box
   automation still owed: StockTwits + cache-backup system timers need
   `sudo`; FA monthly freeze before 1 Oct; delete stale Artifact Registry tags
   (keep `4cca795`, `04efba8`).
2. ~~**Universe read path**~~ **DONE 2026-09-05** (7e7d88b): chains from
   per-underlying parquet-predicate slices; derive writes sorted row groups.
   Gate: 200/200 sampled chains identical (order included), 205 → 0.74 ms
   per call (278×), 201k resident rows vs 5.2M; NOW rebuilt row-identical
   (see HANDOFF). Every later generation rides it.
3. **Cheap verdict changers**: ~~0.45-threshold walk-forward~~ DONE
   2026-09-05 — REJECTED (fold 3 picked 0.45 on validation, then +82%/45%
   DD on test vs ev/0.05's +453%/8%; EXPERIMENTS); DD-brake live
   enforcement in `v4_scan` — DEFERRED: the scanner only alerts (no sizing
   path exists to enforce in); both live bundles are unbraked; revisit when a
   braked bundle is a candidate. ~~v3/v31 watchlist hook~~ (done in c3ba880).
4. **Pool `v6` SCAFFOLDED 2026-09-05** (6656d46): window/train start
   2024-12-01, shares `data_cache_v5` + the PIT universe, `artifacts_v6`; v5
   config untouched (spec hash 4a1897559fe2 verified; `_config_hash` now
   scopes grids to the pool's own families). Window kept EQUAL to v5's on
   purpose (additive reuse must be byte-identical); the 2024-12 start is a
   v7 (from-scratch) item. Partials-by-window: moot while windows are equal;
   revisit for v7.
5. **Generation v6, additive** — families CODED 2026-09-05 (`keltner`,
   `bbw_squeeze` in `signals/tv_signals.py`, grids, seam-tested).
   **Weekly-expiry DTE variant CODED** (`nn_meta/weekly_expiry.py`:
   `DTE_GRID_WEEKLY=[2,4,7]` appended for M/W/F names — 15 on the v5 archive, `WEEKLY_DTE_ENABLED`
   for pool v6; freeze writes `spec["weekly_symbols"]`, build reads it).
   **Additive reuse CODED** (`build_meta_dataset --reuse-rows-from v5`: takes
   the ten v5 families' rows+marks per symbol, builds only the new ones).
   Still to do, in order: (a) rebuild the Batch image (read path + these);
   (b) freeze v6 = the two new families for all 441 + the 25 weekly names'
   full grid re-freeze (the weekly DTEs change their best_strategy/DTE);
   (c) merge into `artifacts_v6/baseline_spec.json`; (d) build with
   `--reuse-rows-from v5` (box + Batch); (e) ladder on the box. NOTE: the 25
   weekly names' OLD families are re-frozen too, so their rows must be
   rebuilt, not reused (reuse only families whose spec entry is unchanged —
   enforce by comparing spec params before reusing: TODO before (d)).
6. FA seat overlay + `[fa]` digest (exit metric is time-gated: 3 monthlies).
7. Vol-regime stage 3 (must beat HAR-RV QLIKE 0.117 per regime).
8. spx0 — parked until the Massive Advanced upgrade lands (2022 bear data).
9. Stacked blend, then RL sizing — last.

Everything below runs with `NN_META_POOL=v31` unless said otherwise; v5 work
uses `v5`; heavy freezes on GCP Batch, everything else on the box.

## 1 — spx0 seat, round 3 (wave-2 item 2) — IN FLIGHT

- [x] Round 3 DONE 2026-08-24 (EXPERIMENTS): **first signs of life** —
  folds 2/3 positive after costs (+2.7%/+10.2% test), no blowups (the
  vertical −1×margin floor held; worst marked DD 36%). NOT a seat yet:
  fold 1 −50.6%, best deflated Sharpe 0.20, fold-3 marked DD 28.6% > cap.
- [x] **Composition diagnosis DONE 2026-08-24** (EXPERIMENTS): verticals are
  selectable raw material, longs are not; vwap_rev flood adds toll; positive
  cells = ma×verticals and gap_fill_50×longs, consistent across the axis.
  strategy seats actually entered — dataset + reports in
  `out/spx0-20260824T145751Z-41a00/`): cheap, shapes round 4.
- [x] Round 4 (concentrated grid) DONE 2026-08-24 (EXPERIMENTS): fold 2
  jumped to +48.5% (deflated 0.17) but fold 3's validation refused every
  candidate and fold 2's marked DD breaches the cap — regime instability,
  not toll, is now the binding problem. No seat after four rounds.
- [ ] USER DECISION: lever 5 (2022 bear data — blocked on the Massive
  Advanced upgrade the user is evaluating) vs PARK with the machinery kept
  (bounded verticals, seat mapping, package fills are durable either way).

## 2 — Dual-mode cadence, panel-wide (wave-2 item 5; v4 seat DONE)

- [x] v4 seat shipped 2026-08-24: recording in every pass, daily top-10
  `--digest` (20:10 UTC weekdays), underlying-direction hit-rates.
  **Watch Monday:** first populated digest + first real `[v4]` alert
  behavior (threshold ev/0.05 through the EV head).
- [x] v3/v31 seats record scored signals + one panel digest — DONE in
  c3ba880 (2026-08-24; `nn_meta/live/scanner.py` → Watchlist); ticked
  2026-09-05.

## 3 — FA-discovery seat (wave-2 item 4; exit metric: ≥3 frozen monthlies)

- [x] Composite ranker BUILT 2026-08-24 (`fa/ranker.py` for real:
  corroboration ≥2 families, liquidity floor = universe_300, point-in-time,
  write-once freeze; tz-robust scores). Fundamental overlay (filings LLM /
  Form 4 / unusual-options) still a stub — heuristic social+news v1 ships
  first per spec.
- [x] **FIRST monthly Top-10 FROZEN 2026-08-24** (`fa/artifacts/
  top10_2026-08.{json,md}`, EXPERIMENTS row). Exit metric: 1 of ≥3.
- [x] Forward tracker code ready (`fa/tracker.py`: windowed excess vs the
  training-universe basket, never guesses missing bars); first meaningful
  run ~late September.
- [ ] Monthly freeze automation — must run on the HOME box, not the server:
  frozen artifacts are git-tracked, and a server-side write would dirty the
  server repo and wedge pulls (the scp lesson). Shape: systemd timer
  (Persistent=true, like healys-stocktwits) on the 1st → rsync-pull
  `fa/archive` from the server → `fa.ranker --prior-month --freeze` →
  commit+push. Until then: manual, ~1 min on the 1st.
- [ ] `[fa]` digest to Telegram + WSB daily trending digest; fundamental
  overlay legs (filings deltas, Form 4, unusual options).

## 4 — Vol-regime track (wave-2 item 3) — first big Batch job

- [ ] Design the realized-vol feature build (v3/data 5.4 GB, 2017→ →
  9y intraday RV) and the HAR-RV/GARCH OOS harness; launch on Batch.
  Product: `available_at`-stamped vol features for every expert; a seat
  only if a sequence model beats the boring baselines per regime.

## 5 — Methodology debt (small, unblocks future verdicts)

- [x] PBO report wiring DONE 2026-08-24: CSCV over the whole policy grid
  (equal-weight daily candidate P&L on validation), reported per run
  beside deflated Sharpe; never guesses on thin windows.
- [x] v5 wide pool DEFINED 2026-08-24 (`PROPOSAL_STRATEGIES_V5`: all 10
  swept families, seam-tested; `NN_META_POOL=v5` plumbs through).
- [x] **PIT universe BUILT + FROZEN 2026-08-24** (all 4 spec steps,
  EXPERIMENTS row): `nn_meta/universe_pit.py` + crawler + 496-day
  backfill → 21 frozen monthlies 2024-11→2026-07 (~300 members, canaries
  X/SWTX/WBA pass, renames FI→FISV & BITF→DRAM aliased); `--membership`
  wired into build_meta_dataset + walkforward_meta (default ON for v5).
  **v5 is unblocked.** Ongoing: monthly crawl+freeze must ride the same
  home-box automation as the FA monthly (block 3) — the entitlement
  window rolls, so crawl promptly each month.
- [ ] DD-brake live enforcement in `v4_scan` sizing (brake is shown, not
  enforced; moot for V118's `dd_brake=None` but a landmine for any braked
  future bundle).

## 6 — v5 wide-pool campaign (IN FLIGHT since 2026-08-26)

The generation the PIT universe unblocked: 10 families × 441 PIT members,
all stages on GCP Batch + the home box. Live detail (job ids, relaunch
commands, infra traps) lives in `HANDOFF.md` — this is the checklist.

- [x] **Freeze DONE 2026-08-29**: 453/453 tasks, zero failures, ~75h,
  ~$40. Merged spec published to `artifacts_v5_in/baseline_spec.json`:
  441 symbols frozen, 12 skipped-thin, every family is somebody's
  best_strategy (rsi 182 · stoch 49 · bbands 46 · volume 42 · squeeze 40
  · supertrend 39 · ma 28 · elliott 11 · macd 3 · tv_rating 1).
- [x] Per-family build checkpoints (`--partial-dir`) + bucket partial
  sync — spot preemption costs ~40min, not ~8h. Kill/resume validated.
- [x] Home box as a third build worker (`run_build_v5_local.sh`, walks
  the spec backwards; bucket skip-check is the only coordination).
- [x] `submit.sh` fails closed when the image tag has no manifest.
- [x] **Dataset build DONE 2026-09-04 16:55Z: 441/441 rows + marks.** Cloud
  fleets drained to 426 (11 spot-preemption deaths), user ended them 12:40Z;
  the box built the 15 stragglers in ~4h (3–4 workers, service-resumed
  across a reboot). Zero build failures.
- [x] Stragglers reconciled 2026-09-04: spec 441 == bucket rows 441 == marks 441.
- [x] **Marks coverage audited 2026-09-04 over ALL 441 symbols** (not just
  the window): every executed trade id present in its marks shard (min
  coverage 100%), zero orphan mark ids. Nothing rebuilt. `logs/marks_audit_v5.csv`.
- [ ] **FIRST THING next campaign — the universe read path** (user decision
  2026-09-02). All measured on the live v5 universe, not estimated. Three
  changes at three layers; together they attack BOTH constraints the v5
  build hit (RAM ceiling and per-call scan cost).

  *The problem.* `universe.parquet` is 5,214,222 contracts / 44 MB on disk.
  A symbol build only ever needs its OWN underlying — 21,009 rows, **0.4%**
  (verified: `Execution.select`, `options/execution.py:89`, always passes
  `self.symbol`). But today every worker loads the whole thing and every
  lookup scans the whole thing:
  - `HybridProvider._get_universe` (`options/data/hybrid_provider.py:96`)
    reads the parquet per PROCESS → **0.96 GB resident per worker**, then
    `u = self._universe.copy()` to normalize 3 columns → peak RSS
    2.53 → 3.17 GB (~0.64 GB transient spike).
  - `get_chain` (`hybrid_provider.py:120`) builds boolean masks over all
    5.2M rows on EVERY call: **216 ms/call vs 0.70 ms on a per-symbol
    pre-filter — 310x**. `Execution._chain_cache` memoizes on
    `(as_of, right, target_dte)`, so misses are per trade-date and per
    roll: order 10^3 scans/symbol ≈ **15–40 min of the ~126 min/symbol**.

  *The fix, in dependency order:*
  1. **Derive sorted/partitioned** — `v3/derive_contracts.py:109` writes
     `uni.to_parquet(...)` straight from a dict iteration, so underlyings
     are scattered and every row group is mixed → pyarrow can skip NOTHING
     and predicate pushdown is useless. Add `uni.sort_values("underlying")`
     before the write (row-group stats become meaningful) or
     `partition_cols=["underlying"]` (one small file per symbol).
     **This one is a prerequisite — steps 2–3 underdeliver without it.**
  2. **Read only what the worker needs** — load with
     `filters=[("underlying","==",sym)]`. 0.96 GB → a few MB per worker;
     the `.copy()` spike becomes irrelevant. Per-worker RSS ~5.4 → ~4.4 GB
     → 4 workers becomes 5–6.
  3. **Keep `get_chain`'s API, fix its target** — mask the per-underlying
     slice, not the full frame. Callers and tests unchanged.

  *Not a data-acquisition problem.* universe.parquet is derived offline
  from flat-files already on disk — no REST, no quota. Flat-files are
  already the documented optimal bulk path. No Massive plan or endpoint
  change helps here (checked 2026-09-02).

  *And not a C++ problem.* The masks already run in numpy/Arrow C++,
  vectorbt sims are Numba-JIT, training is TF/LightGBM. A rewrite buys
  maybe 2–5x on genuine Python overhead, costs months, and re-risks
  diff-gate-validated code — against 310x for ~20 lines of Python.

  Deliberately NOT done mid-campaign: touching the data path with symbols
  in flight is the pattern that cost three fleet rebuilds in the v5 build
  stage. Note step 1 means re-deriving (or one-shot re-sorting) the
  universe, which workers currently hold open.
- [ ] Before the NEXT generation: move `WINDOW_START`/`TRAIN_START` to
  2024-12 (~20% of the current train span is built then dropped by the
  membership filter), and key family partials by window (or clear
  `out/v5/meta_partial/` on any window change — stale partials would
  silently mix windows within one symbol).
- [x] Membership-vs-`assign_split` ordering SETTLED 2026-09-04: benign.
  Both `assign_split` (build) and `assign_purged_splits` (evaluate) decide
  each row from its OWN `entry_ts`/`exit_ts` only — no cross-row state —
  and `membership_mask` is a per-row (symbol, month) filter, so the two
  commute: filter-then-split == split-then-filter row for row. The
  evaluate ladder's fold splits are trustworthy as-is.
- [x] **Assembled on the box 2026-09-04 17:02Z** (`--membership` ON): 2,113,590
  rows (membership kept 2.17M of 3.79M; 1.62M outside PIT membership),
  marks 24.7M rows over 1.33M trades; train/val/test 1.37M/306k/442k rows,
  262/58/96 days; label win 40.1%. ~5 min, 5.3 GB peak. Published to
  `out/v5/meta_dataset{,.marks}.parquet`.
  Original item: Assemble (`--membership` ON for v5) → `out/v5/meta_dataset.parquet`,
  **on the home box** (user decision 2026-09-03, DECISIONS). Pull all
  row+marks shards down first (~1 GB — most exist only in the bucket).
  Watch memory on the mark stream: v31's 88M rows died on the OLD box via
  `pd.concat`; the shipped path streams through a `ParquetWriter` (~0.2 GB
  peak) and v5 has ~4x v31's symbol count.
- [ ] **Determinism check before trusting any box-trained bundle** — run
  evaluate twice with identical seeds and diff the `SHA256SUMS.txt` both
  modes already write; byte-identical = no silent bit flip. (The stronger
  memory check is DONE: memtest86+ passed 0 errors / 6 passes on
  2026-09-04, so this is now a cheap belt-and-suspenders for non-RAM
  nondeterminism, not the RAM gate it was.)
- [x] Determinism check PASSED 2026-09-04 17:08Z (2× `--smoke --folds 1`,
  reports + manifests byte-identical; `nn_meta/reports_v5/determinism/`).
- [x] **Walk-forward evaluate DONE on the box 2026-09-04 17:30Z** (~21 min
  for 3 folds, 8.5 GB): nn wins all three, all gate-eligible via ledger.
  Test: fold 1 filter/0.55 +74.1% (DD 36.7%, marked +71.5%/34.5%, DSR
  0.06); fold 2 ev/0.05 +320.8% (DD 37.3%, marked +321.1%/39.6%, DSR
  0.92); fold 3 ev/0.05 +452.8% (DD 8.4%, marked +500.6%/10.7%, DSR 0.98).
  No negative fold (v31: −11% / 75% DD on fold 2). Score-decile inversion
  flagged on folds 2–3 (EV-head deciles noisier than v31's). Published
  `out/v5/evaluate-20260904T173053Z-box/` (+ SHA256SUMS).
- [x] **Finalize DONE 2026-09-04 18:39Z — REFUSED** (bundle dir redirected to
  `model_final_v5/`; V118 in `model_final_v4/` untouched). Cheap-seed nn
  ev/0.05 +421.8% eligible → 40-seed ensemble +201.3% INELIGIBLE: the
  ex-top3 bar on the May–Aug validation tail is +381.9% (baseline +2781%).
  Verdict entry at the top of `docs/EXPERIMENTS.md`.
- [ ] **USER DECISION — redefine the gate's beat-baseline term.** Shown
  2026-09-04 (`scripts/gate_bar_sensitivity.py`): the ex-top3 bar is a
  5-slot draw whose value swings −66%…+283% when only equal-timestamp
  ties are reordered; the refused ensemble (+201%, maxDD 16%) beats 7 of
  8 re-draws. **Runs (a)/(b)/(c) + 0.20–0.90 confidence sweep DONE
  2026-09-04 evening** from one training (`policy_gate_sweep.md`): (a)
  risk-aware discriminates (passes filter ≤0.45 + ev/0.05 family only);
  (b)/(c at 5–10%) have negative bars here and pass losers; P(win) never
  exceeds 0.65 so "70% confidence" keeps nothing; filter/0.45 (+355%,
  24% DD) was never in the grid. Recommendation: adopt (a). Decision →
  DECISIONS entry → `GATE_BAR=risk` finalize (~1h) persists ev/0.05 as-is;
  optionally add 0.45 to KEEP_THRESHOLDS and re-run the walk-forward
  (~21 min) first.
- [x] **USER DECISION 2026-09-04: gate (a) adopted** (DECISIONS; `GATE_BAR=risk`
  default). **Finalize ELIGIBLE 2026-09-05 00:47Z → first v5 bundle** in
  `nn_meta/model_final_v5/` (nn×40, ev/0.05, val +201%, DD 16.4%);
  published `out/v5/finalize-20260905T004700Z-box-risk-ELIGIBLE/`.
- [x] main fast-forwarded to the branch and pulled on the server 2026-09-05
  (no live-path code changes; requirements unchanged). Server keys refreshed.
- [x] **v5 DEPLOYED as a paper expert 2026-09-05** (user decision): `[v5]`
  seat on the server beside v3/v31/v4, own state + watchlist, in the panel
  digest and heartbeat. Forward record vs V118 decides promotion (~3 months). (scanner reads
  `model_final_v4/`; would need a pool-aware bundle path + server sync +
  paper phase like v4's). Optional first: add 0.45 to KEEP_THRESHOLDS and
  re-run the walk-forward (~21 min) — filter/0.45 was the sweep's best row.
- [ ] Post-campaign: delete stale Artifact Registry tags.

## Massive Advanced — using the new data (PROPOSED 2026-09-05, awaiting the user's order)

Probed live 2026-09-05 (DOCUMENTATION → Data limits): option minute/day
aggregates and trades have FULL history (2017+ verified, bucket 2014→);
quotes from 2022-03-07 (flat files 85–140 GB gz/day → targeted REST only:
`/v3/quotes/{ticker}` ~3.9k quotes per contract-day, 222 ms/call, 8-way
parallel fine); real-time chain snapshots with greeks/IV/OI; websockets
real-time (parked: the panel decides on closed 15m bars); MCP via OAuth.

- [ ] **D1. Live scanner: greeks + quotes in the alert path** (~1 day, all
  four experts benefit today). `Execution.select` already targets
  TARGET_DELTA=0.50 and falls back to moneyness because chains had no
  greeks → use `/v3/snapshot/options/{underlying}` (real-time on Advanced)
  for delta-targeted contract choice, an IV/OI/spread liquidity filter, and
  bid/ask + spread in the Telegram text. Rare calls (per alert), no quota risk.
- [ ] **D2. Deep minute-aggs archive 2017→** (box crawl, ~15 GB, quota-free,
  overnight; extend `v3/flatfiles.py` / `build_universe_daily` windows).
  Unblocks two parked items at once: **spx0 lever 5** (2022 bear regime —
  `data_cache_spx0` is built from these 1-minute files) and the **v7
  from-scratch generation** on a 2020→2026 (or 2017→) window: ~4× the
  labels, several regimes instead of one — the answer to "regime
  instability is the binding problem" (spx0 round 4, v5 fold 3). Also
  backfill the PIT universe monthlies from `day_aggs_v1` 2017→.
- [ ] **D3. Quote-verified ledger** (~2–3 days; changes verdict realism).
  Today fills are worst-print OHLCV (`v4_accounting`: slippage 5 bps,
  half_spread 0 base / 25 bps stressed). For the trades that MATTER — the
  ledger's selected trades on validation/test (hundreds per fold + rolls,
  thousands of REST calls, minutes) — fetch observed bid/ask at entry and
  exit timestamps and book buy-at-ask / sell-at-bid; report ledger returns
  both ways and make the quote-verified one the gate basis (DECISIONS
  entry). Training labels (1.3M trades) keep OHLCV fills but get a
  **spread model** (half_spread by moneyness × DTE × liquidity bucket)
  calibrated from sampled quote days, replacing the flat 0/25 bps.
- [ ] **D4. Trades flat files, 2y (~25 GB)**: (i) fill realism — actual
  prints inside the fill bar instead of bar extremes; (ii) decision-time
  liquidity features (prior-bar print count/size, available_at-safe);
  (iii) a cross-check that v5's executed fills had real prints (the
  2026-08-19 biased-drop lesson, from the other side).
- [ ] **D5. Deeper surface features**: `build_surface` from `day_aggs_v1`
  2017→ so IV/term-slope/put-call features exist for the v7 window.
- [ ] Skip: bulk quotes crawl (100 GB/day); websockets until an
  auto-execution or intraday seat exists. Optional: `claude mcp add
  --transport http massive https://mcp.massive.com/` (OAuth; research
  queries only — the pipeline stays on REST/flat files).

Suggested order: D1 → D2 (start the crawl first, it's unattended) → D3 →
D4 → then v7 + spx0-2022 ride on D2. Decisions for the user: v7 window
start (2020-01 vs 2017), and whether D3 becomes the gate basis.

## Alpaca Algo Trader Plus — what it changes (probed 2026-09-05)

Probed with the box's (paper) keys: SIP bars real-time (the free tier
already served SIP for anything older than 15 min — the v5 cache bars ARE
SIP, verified bar-for-bar — it only withheld the live 15-minute window);
SIP history to 2016 unrestricted; REST 10,000/min (was 200); stock
websockets unlimited symbols (1 connection); options OPRA websocket
(≤1,000 quote symbols, no wildcard) + chain snapshots (no greeks in the
sample — Massive's snapshot has them); option bars only from 2024 (Massive
stays the options-history source); News API (Benzinga) + screener
(most-actives/movers) work; paper account is options level 3.

- [x] **A1 DONE 2026-09-05 (and a much bigger bug with it):** the loader's
  day-keyed cache made the panel scan the previous session all day since
  2026-07-05 (EXPERIMENTS). Fixed: cached history ≤ yesterday + today from the
  streamed bar store / forced REST. Verify Monday per HANDOFF checklist.
- [x] **A2 DONE 2026-09-05:** SIP 1m bars streamed for 443 names → barstore
  (parity-identical 15m bars); OPRA quote stream for a dynamic watch file.
  Original A1 text: **Scan the just-closed bar** (biggest live win, ~half a day). The
  loader passes no `feed`; on the free tier the newest 15 minutes were
  withheld, so the `*/15` pass at :15 could only see bars closed by :00 —
  every expert acted one bar late. Verify on Monday's logs (bar_ts vs
  recording time in the watchlists), then make the loader request
  `feed=sip` explicitly and confirm the pass at :15 scans the :00–:15 bar.
  If the lag is confirmed historically, note it in EXPERIMENTS: paper
  hit-rates before 2026-09-08 carried a 15-minute handicap.
- [ ] **A2. Bars over websocket → near-instant passes** (optional, after A1):
  one SIP connection, `bars` channel for the 441 v5 names (unlimited
  symbols), filling the same 15m cache the REST loader fills; the v5 pass
  drops from ~2 min of REST fetches to seconds. Only worth it once a seat
  is time-sensitive; REST at 10k/min is not a bottleneck today.
- [x] **Live feeds DEPLOYED 2026-09-05** (`nn_meta/live/feeds`, REALTIME_SPEC):
  SIP bars → barstore → loaders; OPRA quotes → quotestore (idle until D1
  registers contracts); heartbeat lines; crons :01/:02/:03 staggered with
  `--workers` 3/2/2/1; BRKB fetch alias fixed.
- [ ] **A3. Paper execution seat on Alpaca** (design item, the real use of
  the trading API): route `[v5]`/`[v4]` alerts to Alpaca PAPER orders (level
  3 covers longs and spreads) so the forward record uses Alpaca's NBBO
  paper fills instead of the in-repo `PaperLedger` simulation. Needs: a
  contract resolver (`/v2/options/contracts`), order sizing rule, exit
  logic (the ledger's DTE/roll rules), and a reconciliation digest.
  Promotion evidence for v5 (TODO block 6) gets much stronger.
- [ ] **A4. Alpaca News + screener into the FA seat**: Benzinga news as a
  third collector beside Finnhub/AlphaVantage (`fa/collectors/news.py`),
  and `most-actives`/`movers` as a daily liquidity/discovery input for the
  ranker and the WSB trending digest.
- [ ] Skip for now: OPRA option websockets (Massive REST snapshots cover
  the per-alert quote need; a live seat would revisit); live-account keys
  (the `.env` keys are paper keys — live orders are a separate decision).

## Forward-tracking duties (standing, this phase)

- Scoreboard reads: `[v4]` real-alert hit-rate vs its paper history; the
  watchlist digest's 7-day rates once they populate; v31's
  outlier-fragility question answers itself here.
- Fold-3 regime miss (noise vs real weakness) — answered empirically by
  per-expert forward tracking, not by another backtest.

## Next generation — user notes 2026-09-05

- [ ] **New proposal families** (user likes the bbands family's win rate: 62.5%
  on 8 v5 finalize trades, +41% mean; 46 symbols' best_strategy in the freeze):
  1. **Keltner channel** breakout/mean-revert on its own (EMA ± k×ATR; the
     Keltner half of the existing squeeze but as an entry family) —
     `indicators/` has ATR via `ta.squeeze_momentum`; new `signals/keltner.py`
     + `SWEEP_GRIDS["keltner"]` (window, atr_mult).
  2. **Bollinger Band Width squeeze** (BBW = (upper−lower)/mid at a percentile
     low → breakout entry; TradingView "BB Width" logic) — distinct from the
     current `squeeze` family, which is already **LazyBear Squeeze Momentum**
     (`signals/tv_signals.py::generate_squeeze_signals`, BB-inside-Keltner
     release + momentum sign, bb_mult × kc_mult swept). So "Squeeze Momentum
     from TradingView" is DONE; Keltner-alone and BBW-squeeze are the adds.
  Both ride the v5 machinery unchanged: family in `PROPOSAL_STRATEGIES_V5`,
  grid in `SWEEP_GRIDS`, seam test, freeze on Batch/box, rebuild rows.
- [ ] **Weekly expirations in the DTE grid.** `DTE_GRID = [1, 5, 10, 30, 45]`
  already has short DTEs (the v5 finalize book entered only 30/45: 13 + 141
  trades — the EV head preferred them; 1/5/10 exist in every row). What is
  NOT modelled: symbols with **Mon/Wed/Fri expirations (3 per week)**. Audit
  2026-09-05 on `data_cache_v5/contracts.parquet`, corrected the same day
  (per-symbol median over the 180 days ending at the last listing date):
  **15 of 441** v5 names truly list 3+/week (AAPL AMZN AVGO GLD GOOGL IBIT
  IWM META MSFT NVDA QQQ SLV SPY TLT TSLA); AMD/EEM/EFA/INTC/MU/SMH/SOXL/
  TQQQ/XLE/XLF show occasional M/W listings but median 1/week — not weekly. Design:
  an expiry-native DTE variant ("next 1st/2nd/3rd expiration" instead of a
  fixed DTE) for those 25, keyed into the `dte` column like the spx0
  variant codes, so rank/EV dedupe and fold selection work unchanged;
  `Execution.select` already picks the nearest listed expiry to a target DTE,
  so the change is the target list, not the fill engine.

## Parked (unchanged)

- Point-in-time universe selection (survivorship fix) — first candidate
  for the next research generation on Batch.
- Deeper options history (2017→) — provider entitlement, not code.
- Stacked blend (track 4) behind wave-2 outputs; RL sizing (track 3) last.

## 2026-09-10 alert exit guidance

- [x] Shared entry-alert exit line with frozen family params and simulator stop.
- [x] Optional fresh-delta premium estimate, explicitly approximate.
- [x] User-confirmed taken-position exit watch implemented; expert paper-ledger settlement remains separate.

## 2026-09-10 user-confirmed exit watch

- [x] Telegram Taken button, reply/manual taken commands, optional actual fill.
- [x] Persistent sell list and user-confirmed sold state.
- [x] Replay saved underlying policy on closed bars and send exit notifications.
- [x] Separate exit notifications from entry ranking; sequential monitor workers.

- [x] Live Robinhood per-contract/per-side fee estimates, account tier and index
  exchange tiers; entry cost and fresh-bid net P/L display, isolated from training.

## 2026-09-10 actual trade accounting

- [x] Code actual sale fills, partial exits, fee completion, realized P/L and read-only broker-record comparison on isolated ops branch.
- [ ] Deploy and verify actual accounting with user-supplied broker records. See docs/reviews/2026-09-10-trade-accounting.md.

- [x] Synthetic full-session/recovery acceptance, including actual partial sales and restart; fix same-bar recovery and quote outage handling.
- [ ] Observe captured live-session behavior and compare actual broker records after deployment.
