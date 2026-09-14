# V6 forward paper deployment — September 14, 2026

The user explicitly approved the 15-minute option expiry cutoff for experimental
paper alerts. The implementation is installed and operating. By 15:05 UTC it
recorded six paper entries, one strategy exit and five open positions; five
allocation cycles completed. The first 13:45 opening pass missed the five-minute
deadline and correctly opened none. A speed improvement is being validated;
do not deploy it without the opening parity/timing checks described below.

- Home runtime: `/home/healy/Coding/HealysV6`, detached Git `0f862bf`.
  Server V6: `/home/mrhea/HealysV6`, branch `ops/v6-forward-20260914`, same commit.
- Server production: `/home/mrhea/HealysBacktester`, branch
  `ops/server-alert-readiness-20260906`, Git `093c117`.
- Home timers installed 13:34 UTC: `healys-v6-forward` (quarter hours +20s),
  `healys-v6-relay` (every minute), `healys-v6-data` (09/11/12 UTC).
- Server `healys-v6-watch.timer` installed; old waiting-only observer disabled.
  The production dispatcher has `NN_META_V6_ALERT_SPOOL` registered. Existing
  expert cron/ranking stays unchanged; its top-five variable lives in cron.
- Home state: `/home/healy/Coding/HealysV6/nn_meta/live/v6_server/`.
  Server receives state under its corresponding `incoming/` directory.
  Home SQLite portfolio owns allocation; server sends immutable paper notices.
- Activation binds 248 test executions (236 runtime/bridge plus 12 subsequent
  expiry/ops rechecks), model/release and 150 runtime files. Three original
  feature cases match all 164 features exactly. Complete 449-name inventory,
  444 current-bar names, 888 candidates, zero errors: fresh REST replay 261.667s.
- Ordinary equity cutoff: 15:45 ET (12:45 early close). Eligible late-close
  ETF options, including SPY/QQQ: 16:00 ET (13:00 early close). Nasdaq/NYSE
  sources and tests are in `nn_meta/live/v6_option_sessions.py`.
- The 13:34 live option preflight found no fresh quote and failed closed.
  A read-only 13:44 diagnostic subsequently found SPY260915C00759000 quotes
  aged 0.091s and trades aged 3.904s. The live runtime rechecks access itself;
  do not explain the first failure without evidence.
- Current data manifest through Sep11:
  `d94a7e6595a4c634be059131a28d92da7fd976006eb4416a0f7ed8d437511969`.
  Premarket full adjusted/raw query passed in 4.91s, no price-vintage change.
- First actual bar: Sep14 13:45:20 UTC / 08:45:20 CDT. It passed real-time
  MASSIVE access but generated 920 proposals and took 379.983s, so no entry
  was permitted. The 14:00 pass opened FXI, USAR, DUOL and BILI; USAR later
  closed through its frozen strategy. ETSY and MDB subsequently opened.
  Evidence: `nn_meta/validation/v6-forward-20260914/live-verification.json`.
- No synthetic alert or broker order was sent. Experimental real paper events
  are authorized. No retraining or separate short-DTE campaign was started.
- Main workspace remains dirty from authorized earlier work; preserve it.
  Preexisting `nn_meta/artifacts_v6/` remains untouched. Source deployed by Git.
  `/tmp/healys-v6-forward-deploy` remains the editable V6 branch worktree;
  the permanent home deployment was added separately because Git worktree
  move cannot cross the /tmp and /home filesystems.

Review: `docs/reviews/2026-09-14-v6-forward-activation.md`.
Previous context: `handoff-history/HANDOFF-2026-09-14-before-forward-activation.md`.
Dashboard: https://stonks-22367.web.app (new paper portfolio not yet in publisher).
Training watcher Telegram remains off, separate from the paper operating watcher.

## Pending performance follow-up in this session

The permanent runtime remains live at `0f862bf` while the main/editable V6
worktrees hold an additional exact reuse optimization. It reuses the eight
identical source calculations between proposal detection and feature building,
skips candidate work when all five slots remain occupied after causal exits,
and preserves the actual stock-query parquet inputs for future replay.
The focused suite passed 109 tests, including exact cross-path reuse equality.

`/tmp/finish-v6-forward-reviewed.py` is running (unified exec session 91931).
It waits between live decision passes, replays the 921-signal retrospective
opening dataset (the later API reconstruction differs by one proposal from
the actual first pass), requires <260s and exact equality of all 164 features
and both prediction heads across 4,722 candidates, then commits/pushes/pulls
through Git, rebinds activation and checks actual server acknowledgments.
It stops without deploying if validation fails. Final state and evidence must
be recorded after that script completes.
