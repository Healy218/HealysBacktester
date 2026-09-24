# Handoff — 2026-09-24 — Stonks V6 paper chart live; V7-2 still building

Read `TODO.md` first. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-v6-paper-chart.md`. V7-1 is
complete under its agreed exclusion policy. V7-2 is still building; V7-3
has not started. Main is the Backtester operating branch. The worktree has
extensive unrelated pre-existing changes; stage only exact owned files.

## V7-2 independent build

`healys-v7-catalog-build.service` remains active under PID 3128252 with
zero restarts at 18:42 CDT, September 24. The latest watcher snapshot is
427/591 complete securities, 1,285/1,773 proposal stores and 2,578 feature
receipts. The restart's 166/166 production-loader preflight passed with zero
failures before workers began. No second builder was started. Monitor using
`./venv/bin/python -m scripts.watch_v7_catalog --follow --interval 5` in a
fresh terminal; a sandboxed one-shot viewer may show service `unknown`, so
use host-side systemd for service state. Full 7-2 source, availability,
variant, compact-size, receipt and disk-reserve audit is still required
after 591/1,773 seals. Do not start 7-3 beforehand. The exact repairs and
remaining audit obligations are in
`docs/reviews/2026-09-24-v7-last45-repair.md` and the archived handoff.
Keep V7 producer sources and the two new last-45 review JSONs byte-stable
while workers run; their hashes are bound into receipts.

## Stonks V6 paper improvement deployed

At `https://stonks-22367.web.app/`, the V6 Paper tab now places a realized
P/L time graph between the broker-style account and trade history. It
reconstructs cumulative realized P/L from dated closed trades and labels
open marks as current-only. The trade table shows opened and closed dates
and sorts by latest activity (close date for closed trades, open date for
open trades). The exporter writes timezone-qualified dates and the same
newest-first order to JSON and CSV. It remains a read-only projection, with
no broker orders.

The live V6 export was manually refreshed at 18:39:44 CDT: 24 trades had
open dates, all 20 closed trades had close dates, rows were descending,
and their realized P/L summed to the account headline. The home publisher
published the refreshed document at 18:40:07 CDT with `issues: []` and
exit status 0. Hosting deployment completed successfully; a live GET of
the site served the new production JS/CSS bundle. Dashboard build and
10 Vitest tests passed; Backtester suite passed 2,384 tests plus 18
subtests. Playwright browser tests could not launch because this machine
lacks the required Chromium headless binary; this was an environment
failure before any test steps.

Backtester exporter commit `8bf7203` is pushed to origin/main. The
dashboard UI commit `f3066f6` is pushed to
`ops/firebase-dashboard-20260911` in the separate
`/home/healy/Coding/HealyLabsDashboard` checkout. That checkout still has
pre-existing uncommitted publisher, training, README and browser-test work;
do not discard or stage it wholesale. The live Hosting bundle was built
from that checkout. The scheduled home publisher source remains in
`/home/healy/Coding/HealysAutomation` and was not changed in this task.

## Next actions

1. Continue monitoring V7-2 service and actual completed securities/stores,
   not just its unstable ETA. Investigate the exact worker receipt if it
   stops. Preserve valid sealed stores.
2. When V7-2 seals fully, run its full gate audit before marking 7-2
   complete or beginning 7-3.
3. If the user wants an account P/L curve including open marks, add a
   timestamped mark-history source prospectively; the currently available
   broker export contains current open marks but no historical open marks.
