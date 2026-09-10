# Session replay and recovery acceptance

The user approved doing session/recovery verification before deploying actual
trade accounting, then proceeding to FA/backup work once broker verification
works. This implementation stays on the isolated ops branch.

The synthetic 390-minute session runs the real on-disk minute store, stream/REST
bar loader, MA crossover and vectorbt exit replay, SQLite tracker, Telegram reply
processor (fake transport), partial/final sale accounting and reconciliation.
It compares all 26 closed-bar prefixes against the historical aggregation twin.
A quiet minute remains absent, a disconnected bucket falls back to forced REST,
restart/backfill repairs the store idempotently, a sale survives failed delivery
and queue restart, and the final 15:45 ET bar produces the exit only at close.
Stale quotes never generate P/L. Final recorded net P/L matches explicit cash
flows and supplied fictional broker records.

Focused failure tests additionally cover stale/forming bars, same-bar recovery,
and quote lookup failure. Existing acceptance tests cover holidays, early closes,
subscription behavior, invalid fills, migration and duplicate command delivery.
External transports are replaced; this is not evidence of an actual full market
session, broker authentication, live websocket reconnection, or exactly-once
Telegram delivery across an ambiguous network timeout. Duplicate sale mutation
is prevented; Telegram cannot guarantee exactly-once message delivery if a send
succeeds remotely but its acknowledgement is lost.

## Repairs found by the harness

1. After a loader failure, a successful retry on the already checked bar skipped
   clearing monitor_error. Retry evaluation when an error exists; recovery now
   clears the error and allows a later distinct failure to alert again.
2. A quote lookup exception prevented persisting a verified strategy exit.
   Treat unavailable quote enrichment as absent while preserving the exit notice.
   Quotes still never create an exit or substitute for recorded fills.

## Repeatable acceptance

```sh
./venv/bin/python scripts/run_session_recovery.py --output /tmp/session-evidence-UNIQUE
```

The output directory must be new. It contains pytest logs, JUnit results and a
receipt with source hashes, Python version, timestamps and exit status. The
receipt explicitly marks live-session and actual broker verification false.
The runner limits numerical-library threads and uses temporary test state.

Local acceptance: 104 tests passed. Evidence:
`/tmp/healys-session-recovery-20260910/`. Full suite result and server deployment
receipt will be recorded in HANDOFF.md. No account details belong in git.

Initial server acceptance: 103/104. The pre-existing weekday-fallback test
read the real host calendar, correctly finding Labor Day closed. Explicitly
mock the absence of a calendar for that test and provide the synthetic session
its own captured calendar. Runtime calendar logic is unchanged.

Final rollout verification at 2026-09-10 16:08:47 UTC: fef6542 deployed,
104/104 server acceptance tests passed, schema and SQLite integrity verified,
monitor/dispatcher schedules present. Private backup and receipts remain under
`logs/ops/accounting-deploy-20260910T155016Z/` on the server; `verified.json`
is the final result. User chose their next sale for real broker verification.
Local full suite passed 694 tests and 18 subtests before the test-only calendar
isolation fix; focused acceptance passed again locally and on the server.
