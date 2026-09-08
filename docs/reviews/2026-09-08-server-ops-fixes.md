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
