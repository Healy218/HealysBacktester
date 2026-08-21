# SPX0 Spec — SPX/NDX daily-expiry options seat (VSPNDX)

**Status:** design frozen 2026-08-21 from the stage-0 audit facts; code lands
in `nn_meta/spx0/` while the v4 EV-head jobs run on Batch. Constraints that
were already decided (ROADMAP Wave 2 item 2, DECISIONS 2026-08-17/19) are not
reopened here; this file records how the builder satisfies them and the new
decisions the data forced.

**One-line goal:** a NEW pool `spx0` — SPX + NDX 0DTE options, calls and
puts, 1-minute bars, signal-driven entries AND exits, multiple trades/day —
through the **same v4 causal contract** (feature availability stamps, purged
splits + embargo, mark-to-market ledger, eligibility gate), with fills
modeled from volume depth and a 25% max-DD gate.

---

## What the data is (audit facts, not assumptions)

- `nn_meta/data_cache_spx0/flatfiles_1m/<day>.parquet` × 500 sessions
  (2024-08-16 → 2026-08-14, only market holidays missing). Columns:
  `occ, timestamp (naive UTC), Open, High, Low, Close, Volume`. Roots
  `SPXW, SPX, NDXP, NDX`; **0DTE volume is entirely SPXW and NDXP**.
- **No bid/ask, no open interest** — trade prints only. Median volume per
  1m bar **3** contracts, p90 ~50; near-ATM 0DTE median ~12. Median near-ATM
  0DTE premium **~0.30** index points ($30/contract).
- Option bars run to 16:15 ET (index options close later than equities);
  the proxy underlying (`underlying_1m/{SPY,QQQ}.parquet`, RTH, index named
  `timestamp`) ends 16:00 ET. Anything after the proxy's last bar has no
  signal source.
- Index underlying is 403-gated → **signals from SPY/QQQ, strikes
  ratio-mapped** (standing decision). The ratio is NOT a constant: it is
  measured per session as `index_proxy_ratio = ATM-strike-cluster / proxy
  close` at the session's first option bar and carried for the day.

## Decisions the data forced (2026-08-21)

1. **Fill model = volume depth, not quotes.** A 1m bar is fillable for `q`
   contracts only if `Volume >= depth_mult * q` (default `depth_mult=2`:
   we take at most half the printed volume). Entry fills at the bar's
   **High** for buys (worst print, no quote), exit at the bar's **Low**
   for sells — the conservative bound the data supports; a stressed
   scenario widens further. A proposal whose entry bar lacks depth is
   **kept with `executed=False`** (rejects are data, as in v31). An exit
   bar lacking depth walks forward to the next bar with depth, up to the
   last option bar of the session, where a 0DTE contract settles to
   **intrinsic at the proxy's 16:00 close × ratio** (cash settlement,
   conservative: no post-16:00 proxy signal exists).
2. **Costs are an explicit, stressed `CostScenario` in dollars, not
   percent.** `fee_per_contract` (broker + exchange + index fees, default
   $1.30 base / $2.00 stressed) and `half_spread_points` (default 0.05
   base / 0.15 stressed on premiums ≤ 1.00, scaled by premium above that).
   On a 0.30 premium the base round trip is ~$2.60 + $10 = **~40% of
   premium** — the seat must clear that. This is the make-or-break number
   and it is stated up front, not discovered.
3. **Position key = (root, right)** — `SPX-C, SPX-P, NDX-C, NDX-P` — so the
   ledger's one-position-per-symbol rule allows 4 concurrent positions
   without stacking the same direction on the same index. "Multiple
   trades/day" is sequential within a key and parallel across keys.
4. **Exits are signal-driven with a hard session floor.** A trade exits on
   the first of: the strategy's opposite/flat signal, a stop (premium ≤
   `stop_frac` of entry), a target (premium ≥ `target_mult` × entry), or
   the session floor (last proxy bar). Stop/target are policy candidates
   selected inside temporal folds like every other choice, never tuned on
   test.
5. **DTE is 0 always** in this pool; `dte` stays an int64 column (the mark
   key casts it), `dte_frac` is minutes-to-expiry / 390.
6. **Feature set** = the 15 existing technicals computed on the proxy's 1m
   bars resampled to 5m (declared `SIGNAL_CLOSE`, same names → no contract
   change), the 4 trade-context features, plus new `SIGNAL_CLOSE` features
   declared in `feature_contract.py` under a `spx0_` prefix: realized vol
   of the last 30/60 proxy minutes, minutes-since-open, minutes-to-expiry,
   option bar depth (`Volume` of the signal bar — known at signal close),
   premium/ratio-mapped-spot. **No surface features** (no daily surface
   exists for the index archive; the 10 `_SURFACE` names are absent, not
   zero-filled — zero-filling a missing feature would silently train on a
   constant).
7. **Gate** = the shared gate with `MAX_DRAWDOWN_CAP` overridden to 0.25
   for this pool (config branch), `MIN_KEPT_TRADES` unchanged.

## Row schema (superset of the v4 contract, emitted from day one)

`symbol` (position key, e.g. `SPX-C`), `root`, `strategy`, `trade_idx`,
`dte`=0, `entry_ts` (signal-close bar), `entry_date`, `exit_ts`,
`direction`, `right`, `contract` (occ), `strike`, `expiration`,
`entry_premium`, `fill_entry_ts`, `fill_exit_ts`, `fill_lag_s`,
`n_fills`=1, `n_rolls`=0, `executed`, `gross_return`, `net_return`,
`und_period_return` (proxy close-to-close over the trade), `exit_reason`,
`depth_entry`, `depth_exit`, the features, `label`, `label_excess`,
`split`. Sidecar `.marks.parquet` (`trade_id, mark_ts, gross_return`) from
the contract's 1m closes between the fill bars, entry and exit marks
guaranteed.

## Pool plumbing

`NN_META_POOL=spx0` → `config`: `DATA_CACHE=data_cache_spx0`,
`INTERVAL=1m`, `DTE_GRID=[0]`, `WINDOW 2024-08-16..2026-08-14`,
`UNDERLYINGS=[SPX, NDX]` with proxies `{SPX: SPY, NDX: QQQ}`,
`MAX_DRAWDOWN_CAP=0.25`, strategies = the v31 proposal list applied to 5m
proxy bars. Everything else (artifact dir suffixing, runs/reports/model
dirs) already works by construction.

## Build order (each tested, TODO block 1c)

1. `nn_meta/spx0/contracts.py` — OCC parse, session ratio, ATM selection.
2. `nn_meta/spx0/fills.py` — depth-gated fill model + `FillFailure` taxonomy.
3. `nn_meta/spx0/costs.py` — dollar cost scenarios; `net_return` from gross.
4. `nn_meta/spx0/build_dataset.py` — per-session builder → rows + marks.
5. config pool branch + feature declarations + `TASK_MODE=spx0-build`.
Nothing launches on Batch before 1–4 are green.

## Second design round (planned 2026-08-21, after the first verdict)

The first design — long ATM 0DTE on the v31 daily-swing strategies run on
5m proxy bars — lost every fold after costs (`docs/EXPERIMENTS.md`
2026-08-21). The model ranks; nothing clears ~40% round-trip friction on
a ~0.30 premium. Levers, in the order they attack that number:

1. **Sell premium (short the contract).** Flips who pays the friction and
   the base rate (~75-80% wins). NOT a sign flip of the builder:
   - A short's loss is unbounded; the ledger debits cash at entry and
     marks value (long semantics). A short position needs a **margin
     notion**: `size_fraction` becomes the margin posted, and the
     position's max loss is capped at that margin by a hard stop
     (`stop_frac > 1`, e.g. 2.0-3.0× premium) — the stop IS the
     risk-limit, selected in-fold.
   - `gross_return` on a short = (entry − exit) / margin, so returns
     stay in the ledger's per-position units and the DD cap still means
     what it says.
   - `spx0_rv_30/60` are the right features for it; realized vol at
     entry vs premium-implied move is the new feature to add.
   - Cash settlement at 16:00 stays (intrinsic against the parity-implied
     level), now as the short's payout.
2. **Exit-policy grid** (open item): `stop_frac` ∈ {0.3, 0.5, 0.7} long /
   {1.5, 2.0, 3.0} short, fold-selectable like DTE was. Cheap; do with 1.
3. **Intraday-native strategies**: VWAP reversion, opening-range breakout
   (15/30 min), gap-fill. Params swept INSIDE folds; the v31 daily params
   on 5m bars are unswept and were a placeholder.
4. **Lower signal bar (1m)**: only after 1 shows life — every extra trade
   pays the same toll, so more trades on a dead design lose faster.
5. **More data (back to 2022)**: a Polygon flat-file pull, ~850 MB per 2y.
   Worth it for the short seat's tail risk (2022 bear regime), pointless
   for a long seat that already loses in calm markets.

Each is its own Batch experiment (<$2). Sequence: 1+2 → verdict → 3 →
verdict → 5.
