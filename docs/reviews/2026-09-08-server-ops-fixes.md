# Server operations fixes — 2026-09-08 review

Review of the Hetzner scanner's first trading day after Labor Day found the
system operationally clean (all four experts completed every cycle, the
top-five dispatcher waited for all four on all 18 batches) and eight things
to do better. All eight are addressed here; production behaviour changes are
listed with their rollback.

| # | Finding | Change | Where |
|---|---|---|---|
| 1 | Option quote feed pinned a core for 3 days with 0 contracts subscribed (alpaca-py busy-waits until the first subscription; nothing ever wrote `option_watch.json`) | Stream idles (heartbeat `state: idle`) until the watch list is non-empty; the alert path now resolves the ~ATM contract to a listed OCC symbol and registers it | `feeds/option_stream.py`, new `feeds/contracts.py`, `scanner.register_alert_contract` called from both experts |
| 2 | Sunday v5 refresh killed at 84% (16 download workers on 8 GB); chained `build_surface` never ran; v5 scanned on an Aug 25 surface with nobody told | `NN_META_DOWNLOAD_WORKERS` env (cron uses 6); `scripts/run_refresh.sh <pool>` records exit status to `logs/refresh_status/<pool>.json` | `config.py`, `scripts/run_refresh.sh`, cron via `scripts/configure_cron.py` |
| 3 | A single quiet minute made `aggregate_15m` reject the bucket; ~190 REST fallbacks per cycle all day (165 of 436 v5 names, incl. GS) | Missing minutes are accepted when SPY/QQQ streamed those minutes (stream provably alive); any other gap still raises → REST | `feeds/barstore.py` (`alive_minutes`, `ALIVE_REFERENCE`) |
| 4 | Wall-clock staleness (30 min) failed all 441 v5 names on the 09:31 ET pass after the holiday | `expected_last_closed_bar` from the captured session calendar; stale = more than one closed interval behind it | `scanner.require_recent_bars`, `StaleBarsError` |
| 5 | X, WBA, SWTX, SAVA, SATS errored every pass (no bars at all) | `NoBarsError` → counted as `skipped`, one INFO line per pass, not an error | `scanner.py`, `v4_scan.py` |
| 6 | Four of 53 top-five slots went to a second strategy on the same symbol+side; v3 title untagged | Slots go to distinct (symbol, side) ideas (`select_top`); `symbol`/`side` columns added (migrated in place); `[v3]` tag | `alert_batches.py`, `scanner.format_alert` |
| 7 | 757 MB of logs, no rotation; every INFO line duplicated into `backtester.log`; TF banners | File handler WARNING+ (`BACKTESTER_FILE_LOG_LEVEL` to override); `BACKTESTER_CONSOLE_QUIET=1` drops engine chatter but keeps `[live]`/`[v4-scan]`/`[notify…]` lines and all print() summaries; `TF_CPP_MIN_LOG_LEVEL=2`; user-cron logrotate (copytruncate, 14 days) | `utils/logging_utils.py`, `deploy/logrotate/healys.conf`, `scripts/rotate_logs.sh` |
| 8 | Heartbeat said "healthy" over 962 errors, an idle options feed, and a dead refresh | Warns on >50 scanner errors, options feed with 0 contracts in RTH, a surface older than 8 days, or a recorded non-zero refresh exit; adds a `surfaces:` digest line | `heartbeat.py` |

Validation: `tests/test_ops_fixes_20260908.py` (26 tests, one class per item)
plus the full suite — 578 passed, 18 subtests. The heartbeat's pass/alert
counters read print() lines, which the console filter never touches.

## Deployment (server, as `mrhea`, no sudo)

Follow-up 2026-09-09 17:10 UTC: the first live alerts registered 11 contracts
at 13:48 and the option stream started — then froze 30 s later at its first
watch-list refresh. alpaca-py's `subscribe_quotes` blocks on
`run_coroutine_threadsafe(...).result()` once running, a deadlock when called
from the stream's own loop (heartbeat stopped, process alive at 0 CPU; the
noon heartbeat flagged it as "191 min old"). Fixed in c1762ab: the refresh
registers handlers and awaits the subscribe/unsubscribe messages itself, and
a stall-guard thread exits after 120 s of loop silence. The hung daemon was
killed; the anchored cron watchdog restarted it within 4 minutes (first
proof that watchdog works), and it is now streaming 235 contracts with ~25k
quotes in the first two minutes.

Outcome (2026-09-09 01:47 UTC): everything deployed, crontab installed 21:06 UTC
(rollback `logs/ops/ops-fixes-20260908T210652Z/`). The v5 download finished in
1.1 h at 6 workers, but `build_surface` was OOM-killed (exit 137) after two
hours: the loader re-factorized the 3.6M-ticker universe per part (2.3 s ×
2,978 parts) and then held all 27.8M rows. Fixed on this branch:
`build_surface_streaming` attaches universe rows by cached index lookup
(1.3 ms/part) and reduces each part to its near-ATM rows and volume sums; the
surface then built in **2 min 40 s** at 1.9 GB RSS (`run_refresh.sh v5
--build-only`, 01:43–01:46 UTC), reported to Telegram by the new
`scripts/watch_refresh.py` (hourly progress, immediate completion). The
heartbeat now reads `surfaces: v3 3d · v31 3d · v5 0d`.

```sh
cd ~/HealysBacktester && git pull
./venv/bin/python scripts/configure_cron.py            # preview
./venv/bin/python scripts/configure_cron.py --run      # backs up to logs/ops/ops-fixes-*/crontab-before.txt
rm -f nn_meta/live/feeds/data/option_stream.heartbeat.json   # stale file from the stopped daemon
nohup ./scripts/run_refresh.sh v5 >> logs/surface_refresh_v5.log 2>&1 &   # resumes the killed download
# once contracts start appearing in nn_meta/live/feeds/data/option_watch.json:
./venv/bin/python scripts/configure_cron.py --run --enable-option-feed
```

Rollback: `crontab logs/ops/ops-fixes-<ts>/crontab-before.txt` and `git checkout 05f8a68`.
The queue column migration is additive; older code ignores the new columns.

## 2026-09-09 — real contract and live quote in every alert (user: "option 1")

User decision: replace the advisory "~ATM near $spot, ~N DTE" line with the
resolved listed contract and its live market, using a Massive REST snapshot
when the OPRA stream has not yet delivered a quote for a freshly registered
contract. Model decisions, P(win) and contract selection (nearest listed
expiry to the target DTE, nearest strike to spot) are unchanged.

New alert block (both experts' formatters, `nn_meta/live/feeds/quotes.py`):

```
contract: MARA 2026-10-09 $11.50 CALL (MARA261009C00011500)
quote: bid 1.26 / ask 1.31 · mid 1.29 · spread 3.9% · 99x31 · 3s old · Δ 0.59 · IV 85% · rest
```

Sources in order: the stream's NBBO when ≤ 3 min old (`source: stream`), else
`MassiveProvider.get_contract_snapshot` (`/v3/snapshot/options/{u}/O:{occ}`,
`source: rest`, also carries delta and IV). REST is only called for alerts
above the expert's probability floor; below-floor candidates get the stream
quote or "quote: unavailable". If the contract cannot be resolved the legacy
line is kept, so no alert is ever blocked by this path. The paper ledger and
the alert queue payload now carry `contract` and `entry_mid`.


## 2026-09-10 — Exit guidance on all entry alerts

User authorized the prior proposed exit-line implementation. Added shared
family rule formatting and raw params through legacy and v4/v5 detection.
Stock stop comes from SIM_CONFIG; opposite-entry reversals are disclosed.
Optional premium stop-level estimate needs fresh valid quotes and signed
delta and states its linear approximation limitations. No premium stop/target
or automated SELL monitor introduced. RSI long below/short above, volume
level condition, and Elliott swing extremes verified against source rather
than the earlier conversational preview.

Validation: full ops suite 616 passed +18 subtests. Updated prior alert line
count expectation and fixed watchlist test clock (expired historical fixtures).
Quote deployment 4a30010 confirmed on production at 2026-09-09 20:12:02 UTC.
