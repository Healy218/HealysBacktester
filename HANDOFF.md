# Handoff — 2026-09-24 — V6 paper dashboard refresh

## Start here

Read `TODO.md`, then this file. The preceding handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-v6-paper-refresh.md`.
V7-2 is still building; do not stop, restart, relabel, delete or deep-audit it
during the run. Do not start 7-3 until all 1,773 stores and the resource and
recovery checks pass. The prior handoff has the 15:50 UTC V7 and V5 censuses.

## V6 paper incident and repair

The user reported that V6 Paper had shown no new account trades for two days
despite opening/closing notices. At 2026-09-24 19:11 UTC, the actual home V6
`portfolio.sqlite3` held 19 closed and 3 open positions, with closes through
18:30 UTC. The dashboard's `V6_BROKER_LEDGER` file was a one-off 2026-09-22
22:53 UTC export with 13 closed and 1 open, while the home publisher continued
successfully every minute. This stale projection caused the visible mismatch.

`scripts/export_v6_broker_ledger.py` now publishes its JSON and CSV atomically.
The enabled `healys-v6-broker-ledger.timer` refreshes the existing projection
at :03/:18/:33/:48 UTC during weekday 12–23 UTC hours. The service reads the
V6 checkout ledger without modifying it and imports the quote client from that
checkout; it writes only the broker projection. At 19:18:49 UTC the service
succeeded with 19 closed, 3 open and 2 freshly marked open positions. The
19:18:56 UTC home publisher succeeded after the new export and reported only
`Latest paper pass failed`. The next projection timer was queued for 19:33 UTC.
The dashboard projection is still stored at the historically dated filename
`v6-broker-ledger-20260921.json` because the publisher's live config points
there. Its `summary.snapshot_at` records actual freshness.

The separate frozen V6 producer intermittently fails closed at `monitor_exits`
when CELH has no fresh post-decision option quote. The 19:00 and 19:15 UTC
passes failed with `unresolved position monitoring; new entries withheld`;
18:00 and 18:45 passes completed. Do not bypass its quote safety rule to fix
the dashboard. Follow up if quote absence persists or position exits remain
unresolved. The paper ledger and notifications continue to update on accepted
passes. Missing fresh marks leave full marked equity unavailable; the
projection labels unmarked positions explicitly.

## Other active work

The V5 server capture backport remains on `ops/server-alert-readiness-20260906`
at `059ff1d`; nine real passes had sealed 3,555 candidate identities and 48
features by 15:47 UTC. Finish the day's pass census and hashes after the last
scan. Paper staging to home still needs the explicit boundary decision. The
incubator after-close timer remains disabled without `--allow-execution`; V7/FA
admission still awaits 7-2 through 7-7 and separate isolation approval.

Main has unrelated V6/V7 dirty source and documentation changes. Stage only
files for the scoped task; do not broad-stage, clean or reset. The V7 catalog
and generated incubator artifacts remain ignored.
