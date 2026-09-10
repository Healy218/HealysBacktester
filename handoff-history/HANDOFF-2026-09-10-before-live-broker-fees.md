# Taken trades and exit watch

2026-09-10. User explicitly approved tracking taken trades AND exit alerts.
Production ops branch remains isolated from the home v6 build on main.
Compact contract/quote/exit alert layout was deployed as 4e5b165 and its MARA
Telegram preview was accepted. The current change adds ✅ Taken buttons,
reply `taken`, `/taken ID [quantity @ price]`, optional `contract OCC_SYMBOL`,
`/selllist`, `/sold ID`, and `/tradehelp`. Old sent-message replies can recover
context only when the exact saved message and frozen parameter label match.

SQLite additive migration retains candidate context and message-ID mapping,
user-confirmed positions and retry receipts. Repeated commands do not duplicate
positions. Quantity/price are optional actual fills, never assumed mid fills.
Exit monitor uses original warmup and saved simulator config, checks closed
trade status, and sends separate exit notices through the minute dispatcher.
Underlying stop / strategy / opposite-entry / expiry notices do not place
orders or mark actual positions sold. User /sold is required. Missing or
unreproducible market data triggers an attention notice and retry.

Install via git pull and `scripts/configure_taken_monitor.py --run`; cron is
:04/:19/:34/:49, sequential expert subprocesses, one compute thread each.
No worker starts for an empty list. RTH grace includes final closed bar.
Server preflight: 4 cores, 6.8 GB available of 7.8 GB; no home workers touched.
See DOCUMENTATION.md for behavior and docs/reviews/2026-09-10-taken-trades.md
for validation/deployment evidence. No actual user positions created by tests.

Deployed `3b790e0` at 2026-09-10 04:25 UTC. SQLite backed up, cron installed,
empty-list launcher verified. Read-only real MARA replay succeeded (still open
through Sep 9 19:45 UTC). No actual positions created. Final suite 640 passed
+18 subtests. Detailed backup/rollback paths are in the review note.

Next user-requested live test: record the user-supplied held contract rather
than the original alert's suggested expiry, retaining the saved exit rule.
Quantity-only commands now support unknown premiums; actual position details
belong only in the server SQLite ledger. See final deployment notes below.

Live user-provided position test completed: actual expiry/strike override,
quantity-only registration, closed-bar replay, then the user's supplied fill
update all succeeded. Position remains open with no monitor error and no exit
through the Sep 9 closing bar. Confirmation and corrected fill receipt were
accepted by Telegram. Actual holding details remain in server SQLite only.
Code deployed: 3afba5c. Full suite: 641 passed +18 subtests.
