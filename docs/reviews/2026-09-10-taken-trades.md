# Taken trades and exit alerts

User requested explicit taken-trade tracking and exit alerts. New entry alerts
carry a Taken button and ID; replies and manual commands record actual held
contracts separately from all expert paper ledgers. Exit watch reproduces the
saved underlying simulator, preserving warmup, stop and reversal semantics.
No order placement or automatic position closure. See DOCUMENTATION.md for
commands, cron, error handling and migration details.

Validation: full ops suite 637 passed +18 subtests. New checks cover Taken,
reply/manual fills, duplicate updates, wrong chats/forged buttons, exact older
message recovery, schema migration, quote contract overrides, delivery retry,
real simulator open-vs-closed trade status, long/short underlying stops,
opposite-entry exits, forming-bar exclusion, changed/missing history, and cron
preservation. Server resource preflight: 4 CPU cores, 6787 MiB available RAM.

## Deployment verified

2026-09-10 04:25 UTC: production fast-forwarded to `3b790e0`. Live SQLite
backup: `logs/ops/taken-deploy-20260910T042519Z/alert-batches-before.sqlite3`.
Cron rollback: `logs/ops/taken-monitor-20260910T042521Z/crontab-before.txt`.
Migration preserved the existing queue; taken-position and message-map tables
started empty. The watcher launcher ran successfully with that empty list.
A read-only MARA/v31 replay recovered MARA261009C00011500 and confirmed the
original strategy was still OPEN through the 2026-09-09 19:45 UTC bar. No
position or Telegram message was created by that check. Legacy display-price
rounding is tolerated within half a cent; replay uses the bar's full precision.
Final complete suite: 640 passed +18 subtests, including attention-notice and
expiry-review tests. User must explicitly mark actual entries Taken.

## First user-authorized held-position test

Quantity-only support deployed as 3afba5c (641 tests +18 subtests passed).
The user's actual held contract override was verified against the option
listing, registered via the same command handler as Telegram, and checked
against real closed market bars. The replay remained open through the Sep 9
closing bar without monitor errors. A subsequent user-supplied premium was
recorded without changing the held contract or duplicating the position.
Both Telegram receipts were accepted. This was an actual user-confirmed
position; its private holding details are retained only in server SQLite.
