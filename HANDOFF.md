# Handoff — server operations fixes deployed; v6 freeze at 314/453

September 8, 2026, 21:20 UTC. Written after the first trading day post
Labor Day. Two things are live and must not be disturbed: the home v6 freeze
and the production scanners.

## Home box — v6 freeze (do not touch)

Campaign `v6-local-20260906`, controller `scripts.run_v6_freeze_trial` PID
2541751. Freeze shards **314/453**, four workers (QQQ, RACE, RBLX, RCAT at
last look), 7.3 symbols/hour, ETA ~**Sep 09 15:58 UTC**. The fifth-worker
trial ran its two hours on Sep 7 and decided `return_to_four_memory_headroom`
(trial 9.2/hour vs 12.0 baseline; memory PSI avg60 1.2%); it stays on four.
Do not change the source snapshot, pinned causal packages or the working tree
under `nn_meta/` while it runs. Post-freeze launchers are prepared and
UNLAUNCHED (`scripts/run_{build,evaluate,finalize}_v6_local.sh`, preview by
default; `docs/reviews/2026-09-08-v6-stage-launchers.md`). Watcher reports every
half hour to Telegram and `logs/v6-progress/v6-local-20260906/`.

## Production — Hetzner, branch `ops/server-alert-readiness-20260906` at 997d668

The eight findings from the day's server review are fixed and deployed —
`docs/reviews/2026-09-08-server-ops-fixes.md` (findings, changes, rollback).
Plus a ninth found while deploying: the feed watchdog crons' bracketed
`pgrep -f "[f]eeds.x"` matched their own `sh -c` line (which also spells out
`-m nn_meta.live.feeds.x`), so a dead daemon was never restarted; the pattern
is now anchored, `pgrep -f "feeds\.x$"`. DOCUMENTATION's Traps and runbook are
updated accordingly.

State at handoff:
- Crontab rewritten 21:06 UTC by `scripts/configure_cron.py --run`; rollback
  copy `logs/ops/ops-fixes-20260908T210652Z/crontab-before.txt` on the server.
- `scripts/run_refresh.sh v5` running since 20:40 UTC (6 download workers,
  ~115k/219k contracts at handoff, then `build_surface`); outcome lands in
  `logs/refresh_status/v5.json` and the heartbeat reads it. The v5 surface is
  still the Aug 25 file until that finishes — v5 alerts today were scored on
  a two-week-old IV surface.
- Option quote stream restarted on the new code: state `idle`, 0 CPU, until
  the alert path registers a contract (`option_watch.json`, written by
  `scanner.register_alert_contract` via `feeds/contracts.py`).
- First `scripts/rotate_logs.sh` run truncated the 392 MB `backtester.log`;
  the rest rotate daily at 04:07 UTC.
- Top-five dispatcher (Sep 8 a.m., Codex): 53 sent / 189 floor-suppressed /
  6 rank-suppressed across 18 batches; from now on slots go to distinct
  symbol+side ideas.

Verify tomorrow (Sep 9): noon heartbeat footer error count near zero (was 962
→ 1171 by close today, mostly the holiday first-pass stale burst and dead
tickers); `surfaces:` line shows v5 0–1d; REST-fallback warnings per cycle
down from ~190 to a handful; alerts still arrive.

Ops-branch source (live path: scanner, v4_scan, barstore, alert_batches,
heartbeat, feeds, logging_utils, config) is NOT on `main`. Merge it into
`main` only after the freeze campaign completes — the campaign imports
`nn_meta` from this working tree for every new freeze process.

Validation: ops branch 579 tests + 18 subtests (26 new in
`tests/test_ops_fixes_20260908.py`); main unchanged at 1452 + 18.

## Documentation pass (this session)

Reviewed the week's notes (handoffs Sep 5–8, reviews Sep 6–8, commits on both
branches). Updated: DOCUMENTATION.md runbook + Traps, DECISIONS.md (Sep 7
fifth-worker trial, Sep 8 top-five routing, launchers, server fixes — none had
been logged), TODO.md section 5/6 ticks, this handoff. EXPERIMENTS.md has no
new row: nothing was evaluated this week; the next row is the corrected v6
result.
