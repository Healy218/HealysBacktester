# Handoff — v6 build and assembly launched

September 9, 2026. User authorized next phase after freeze completion.
Freeze completed successfully at 19:16:04 UTC: 453 verified shards, merged baseline
449 symbols, four explicit skips (CBRS, DRAM, MUU, SNXX). Trial controller result
full-run/worker-trial/result.json: returncode 0, freeze_completed=true. The prior
fifth-worker experiment ended early via the memory guard; it did not complete
a two-hour throughput comparison. Preserve all campaign source/data fingerprints.

Build/assembly launched 20:33:45 UTC using prepared run_build_v6_local.sh --campaign
v6-local-20260906 --workers 4 --run. Detached wrapper PID 1193901; original research
launcher PID 1193987/start 27194439. No evaluation or final training launched.

Actual launch sizing: 24.56 GiB MemAvailable; four slots at 5 GiB each plus 4 GiB
reserve. Two physical cores/SMT siblings excluded (CPUs 1,4,9,12). Worker allocation
uses remaining 12 logical CPUs. This is admission sizing, not a hard RAM cap.
At last verification the launcher is in expensive input validation, reading
~127 MB logically/~65 MB physically over 2 seconds. No build worker had started
yet; the launcher automatically starts four once all original gates pass.
Coverage preflight passed 500 option/underlying days with neither missing.

Evidence under nn_meta/campaigns/v6-local-20260906/v6/runs/next-stage/:
- build-launch.json: detached PID, exact command and log path.
- build-plan.json: actual CPU/RAM sizing and sealed expanded input digest.
- build-launch-20260909T203345Z.log: wrapper startup/errors.
- build.log: original stage launcher, input checks, build and assembly output.
- build-result.json appears only after build+assembly return. Inspect exit code.
Per-symbol outputs/logs retain original meta_rows, meta_marks, partials paths.

Watcher now labels build/assembly launcher, reports 0/4 during verification,
counts builds against 449 eligible symbols, and removes the obsolete halfway
freeze reminder after merged baseline exists. Rate/ETA starts as completions
arrive. Thirty-minute Telegram timer remains active; updated report delivered.
No pinned causal package or original research launcher was modified.
Two historical watchlist tests became date-dependent when their August 18 entries
aged beyond retention on September 9; fixed their test-only clock at existing NOW.

## Production — Hetzner, branch `ops/server-alert-readiness-20260906` at 997d668

The eight findings from the day's server review are fixed and deployed —
`docs/reviews/2026-09-08-server-ops-fixes.md` (findings, changes, rollback).
Plus a ninth found while deploying: the feed watchdog crons' bracketed
`pgrep -f "[f]eeds.x"` matched their own `sh -c` line (which also spells out
`-m nn_meta.live.feeds.x`), so a dead daemon was never restarted; the pattern
is now anchored, `pgrep -f "feeds\.x$"`. DOCUMENTATION's Traps and runbook are
updated accordingly.

State at handoff:
- Crontab rewritten 21:06 UTC by `scripts/configure_cron.py --run` (done); rollback
  copy `logs/ops/ops-fixes-20260908T210652Z/crontab-before.txt` on the server.
- v5 surface rebuilt 2026-09-09 01:46 UTC. The download took 1.1 h at 6
  workers; the first `build_surface` was OOM-killed (exit 137) after 2 h —
  the loader re-factorized the 3.6M-ticker universe per part and then held
  27.8M rows. Fixed on the ops branch (`build_surface_streaming`: cached
  index lookup + per-part reduction; 2 min 40 s at 1.9 GB) and rerun with
  `run_refresh.sh v5 --build-only`. `scripts/watch_refresh.py` reports a
  refresh to Telegram hourly and on completion. Heartbeat now reads
  `surfaces: v3 3d · v31 3d · v5 0d`. v5 alerts on Sep 8 were scored on the
  two-week-old surface.
- Option quote stream restarted on the new code: state `idle`, 0 CPU, until
  the alert path registers a contract (`option_watch.json`, written by
  `scanner.register_alert_contract` via `feeds/contracts.py`).
- First `scripts/rotate_logs.sh` run truncated the 392 MB `backtester.log`;
  the rest rotate daily at 04:07 UTC.
- Top-five dispatcher (Sep 8 a.m., Codex): 53 sent / 189 floor-suppressed /
  6 rank-suppressed across 18 batches; from now on slots go to distinct
  symbol+side ideas.

Verify Sep 9: noon heartbeat footer error count near zero (was 962 → 1171
by close on Sep 8, mostly the holiday first-pass stale burst and dead
tickers); REST-fallback warnings per cycle down from ~190 to a handful;
alerts still arrive; no `⚠️` lines about refresh or surfaces.

Ops-branch source (live path: scanner, v4_scan, barstore, alert_batches,
heartbeat, feeds, logging_utils, config) is NOT on `main`. Keep it isolated throughout this research campaign: build/evaluation also
verify the original campaign source fingerprint. Completing the freeze alone
does not authorize changing its downstream source inputs.

Validation: ops branch 579 tests + 18 subtests (26 new in
`tests/test_ops_fixes_20260908.py`); main unchanged at 1452 + 18.
