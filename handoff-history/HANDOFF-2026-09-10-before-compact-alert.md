# Production exit guidance in entry alerts

2026-09-10 UTC. Ops branch `ops/server-alert-readiness-20260906`, isolated
worktree `/tmp/healys-server-alert-readiness`; home v6 build remains on main.

Real contract + NBBO change `4a30010` confirmed deployed cleanly at
2026-09-09 20:12:02 UTC. This session adds shared `exit_rules.py`, passes raw
frozen params through both scanners, and adds an exit line for all experts.
Actual source semantics supersede Claude's earlier proposed RSI/volume/Elliott
descriptions. Fixed stock stop uses signal close; premium estimate is optional,
fresh, signed-delta-only. No model, training, trade policy, or ledger changes.

Next separate work: paper-position exit monitor and SELL alerts. Entry guidance
does not perform that monitoring. Preserve existing top-five routing,
probability floors, overflow replies, live feed watchdogs, and hourly home
build watcher. Do not merge this branch into the source-pinned home campaign.

Deployed and verified production code `7bc74ec` on 2026-09-10 ~01:00 UTC.
Full ops suite: 616 passed +18 subtests; final exit tests 26 passed.
Read-only server preview passed with a recorded v31 alert. See the server
ops review note for evidence. Next cron passes pick up the formatter.
