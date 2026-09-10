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
