# Handoff — merge integration update, September 5, 2026

The user directed merging the review fixes into `main`, continuing in
`/home/healy/Coding/HealysBacktester`, and doing the TradingView work next,
before rebuilding the research artifacts. Integration validation passed: 642 tests and 18 subtests;
the 535-test count in the preserved notes is the pre-merge result. A local
merge does not deploy the server or launch a freeze/build/training campaign.

The September 5 audit repairs use feature/build contract `2026-09-05-causal-v2`.
Pre-audit freezes, partial checkpoints, rows, marks and bundles must be rebuilt
and validated under that contract; preserve existing files as historical
artifacts, and do not relabel them to bypass verification. Historical returns
and gate verdicts below are not corrected performance evidence. Evaluation
with a globally frozen proposal generator is restricted to periods after its
optimization horizon; it is conditional on that generator, not end-to-end
fold-local refreezing.

The latest operational handoff is preserved verbatim below and separately in
[its pre-merge snapshot](handoff-history/HANDOFF-2026-09-05-before-main-merge.md).
Its report of four deployed experts and paused v6 work describes the earlier
session, not a fresh production inspection. **Do not execute its v6 resume,
merge-shards or v5 reuse instructions with the old artifacts.** Retain the
211/441 partials intact; the corrected campaign needs compatible provenance.
Default loaders reject pre-audit bundles, so deploying source alone can stop
old experts from loading. No server deployment is implied by this merge.

TradingView work is next. The user's go/no-go before shared alert-format
changes remains in force. Keep streamed current-session bars, forced REST
fallback, closed-bar freshness checks, staggered detection workers, and the
v7 offline-twin/parity requirements. NBBO paper execution and quote-verified
historical accounting are still future work. September 8, 2026 is Tuesday;
references to Monday in the preserved handoff are historical date typos.

See [audit remediation](docs/reviews/2026-09-05-remediation.md) and the
[original audit](docs/reviews/2026-09-05-adversarial-audit.md) for implemented
repairs and migration requirements.

---

# HANDOFF — state for the next session

Written 2026-09-05 ~23:45 UTC (18:45 CDT). Protocol: `CLAUDE.md`.
Previous handoff (the whole day: OS-wipe restore, v5 ladder, gate dissection,
v5 deploy, Massive/Alpaca upgrades, live feeds, the blind-scanner bug):
`handoff-history/HANDOFF-2026-09-05-wipe-restore-v5-ladder-feeds.md`.

## The one-paragraph state

**Four experts live on the server (v3 real; [v4] real since 08-24; [v31] paper;
[v5] paper since 09-05), now on STREAMED SIP bars** (`nn_meta/live/feeds`,
two daemons under cron watchdogs) with crons at :01/:16/:31/:46 staggered by
pool and parallel detection. **Until today every expert had scanned the
PREVIOUS session's bars all day** (day-keyed bar cache; EXPERIMENTS
2026-09-05) — the paper record before Monday 2026-09-08 is void as an
intraday record. **v6 additive freeze is PAUSED at 211/441** (user gaming on
the box; resume below). Massive Options Advanced + Alpaca Algo Trader Plus
landed today; plans are in TODO ("Massive Advanced", "Alpaca Algo Trader
Plus"). Suite 535 green. Box, server and GitHub `main` are all on the same
commit; nothing is running on the box.

## FIRST ACTIONS next session (in order)

1. **Monday 2026-09-08 open (13:30Z) — verify the live path is finally
   current.** On the server: `tail logs/feeds_stock.log` shows bars flowing;
   `grep "Loading .* from Alpaca" logs/v5_cron.log` ≈ 0 for today's bars;
   the :16 pass logs act on the :00–:15 bar; the 17:00Z heartbeat shows two
   healthy feed lines and 4 experts with RTH passes. If a feed heartbeat is
   stale, the loaders fall back to REST automatically (still current).
2. **Resume the v6 freeze when the box is free:** `setsid nohup
   scripts/run_freeze_v6_local.sh > logs/freeze_v6_local.log 2>&1 &` (each
   shard skips its done symbols; ~14 h left at 4 workers) and re-enable
   `systemctl --user enable healys-freeze-v6`. Then merge
   (`freeze_baseline --merge "$(ls nn_meta/artifacts_v6/spec_shard_*.json |
   paste -sd,)"`), build with `--reuse-rows-from v5`, ladder on the box
   (TODO block 5/6 + `Next generation`).
3. **Alert-path contract resolution (TODO Massive D1)** — the option quote
   stream idles at 0 contracts until alerts resolve to an OCC symbol
   (Massive snapshot, delta-targeted) and register it in
   `nn_meta/live/feeds/data/option_watch.json`; bid/ask/spread then appear in
   the alert text. User asked for a go/no-go before the shared alert format
   changes.
4. Then TODO order: deep minute-aggs archive 2017→ (unblocks spx0 lever 5 and
   v7), quote-verified ledger, trades files, paper-execution seat design.

## What is where (today's additions)

- `nn_meta/live/feeds/`: `barstore` (1m parquet per symbol per session; 15m
  aggregation bar-identical to REST, parity-checked), `stock_stream`
  (Alpaca SIP bars, 443 names, backfill on start, heartbeat), `quotestore`
  + `option_stream` (OPRA quotes for `option_watch.json`), spec
  `docs/specs/REALTIME_SPEC.md` (v7 real-time contract: offline twin +
  parity gate per intraday feature).
- `nn_meta/live/parallel.py`: spawn-pool detection; `--workers`/`SCAN_WORKERS`.
  Server: v5 3 workers at :01, v4+v31 2 workers at :02, v3 1 worker at :03.
- `run_live._bar_loader`: cached history ≤ yesterday + today from the stream
  (heartbeat ≤ 3 min) or forced REST; `FETCH_ALIASES` applied (BRKB).
- Gate: risk-aware (`GATE_BAR=risk`, DECISIONS 2026-09-04); v5 bundle in
  `nn_meta/model_final_v5/` (tracked); config_hash scoped per pool.
- v6 mechanics: `keltner`, `bbw_squeeze`, weekly-expiry DTEs (15 names),
  `--reuse-rows-from`, additive freeze (`--strategies --base-spec`),
  `scripts/run_freeze_v6_local.sh`; Batch image `04efba8` if cloud is wanted.
- Read path: chains from per-underlying parquet slices (278×); CRWV rebuilt
  byte-identical; NOW differs only by cloud/box libm drift.

## Standing warnings

- Never let the live path read a day-keyed cache for the current session
  (DECISIONS 2026-09-05). Check freshness by the newest bar timestamp, not
  pass counts (memory: live-data-freshness-check).
- Calling `nn_meta.live.heartbeat.build_message()` on the server SENDS a
  Telegram message — use `--dry-run` paths or read the digest code instead.
- `.env` Alpaca keys are PAPER keys (options level 3); live-account keys are
  a separate decision. Massive Advanced: quotes flat files are 85–140 GB/day —
  targeted REST only.
- The box's `data_cache_v5/universe.parquet` is still unsorted (fine: slice
  reads are 0.09 s); `scripts/sort_universe.py` exists for new caches.
- `pgrep -f`/`pkill -f` patterns MUST use the bracket trick (`"[f]eeds…"`)
  everywhere — cron watchdogs, ssh one-liners, monitors. A plain pattern
  matches its own shell: the watchdog never restarted the stock stream, my
  checks reported it alive, and a `pkill` killed my own ssh session.
- Server has no sudo: daemons run via `@reboot` + 5-min watchdog cron lines;
  crontab edits = stage file, diff, `crontab <file>` (backups in `~/crontab.bak.*`).
- Reviewer worktree: `~/Coding/HealysBacktester-review` (branch
  `review/2026-09-05`, sparse, 7 MB); herdr workspace w3 "review".
