# Handoff — October 1, 2026 — V6 paper input repair and timing verification

## Selected user task

User asked to fix V6 so Alpaca paper trading can continue today.
TLT input-vintage failure repaired; new immutable snapshot published 10:45:53.
Actual paper trading resumed (UAL entry and later close verified), but some
8-worker scans missed entry deadlines under shared load. Resource-only v9
completed five observed scans in 261–286 seconds, zero detection errors.
At 14:45 the scanner still withheld entries on missing fresh Massive FLY quotes.
Alpaca broker polling succeeded at 14:46, with one position (26 FLY puts).
This external quote-freshness blocker remains; do not claim all scans healthy.
No change to frozen model, quote freshness, entry deadlines or order policy.

## Paper inputs and evidence

Selected snapshot: `nn_meta/live/v6_server/data/2026-09-30-vintage-20261001-r1/`.
Manifest: `535dde7c63a7bc226a9f34b21b0cda18b8cf051128bbf7611e54b163ab825441`.
All 449 symbol files verified; fresh raw/adjusted overlap passed for 444 available
symbols, five previously unavailable symbols remain explicitly accounted for.
TLT alone had newly restated adjusted history. Original snapshot and activation
preserved. Incremental seed's 7,167,256 raw/adjusted rows each matched exactly.
Historical option-root aliases retained after an unpublished surface-build failure.
Evidence: `nn_meta/validation/v6-paper-vintage-20261001-r0/`, especially `incremental/`.
[Repair, actual fills and timing review](docs/reviews/2026-10-01-v6-paper-vintage-repair.md).

## Selected scanner and actual outcomes

Service `healys-v6-alpaca-scanner.service`; unchanged quarter-hour timer.
Launcher `scripts/run_v6_alpaca_scanner_v9.sh` delegates to unchanged v8 adapter.
Autosizer selects 11 workers now, with 16 GiB maximum / 14 GiB high, no swap;
worker numerical threads remain one. New persistent drop-in `90-resource-v9.conf`.
Paper manifest: `216d61365a3b65c5eccce28e5fe1da9eb408bebd2dc18c0eb47f3241aa77b890`.
Previous manifest/unit preserved in paper `runtime-revisions/scanner-resources-v9-20261001/`.
Actual PYPL exit: 24 contracts at $2.62 in two fills at 10:46–10:47.
Actual UAL entry: 10 at $7.30 at 11:20; exit: 10 at $6.15 at 12:07.
11:45/12:15 scans withheld entries on unavailable fresh UAL option quotes.
12:30 scan missed its entry deadline at 345.372 seconds; this predates v9.
V9 also refused a late-started 13:15 scan; deadlines were not loosened.
Actual FLY entry: 26 puts at $3.20 at 14:06:47. Account showed this position and
zero open orders at 14:35. Missing FLY quotes blocked 14:15/14:30/14:45 scans.
Evidence: `v9-scans.json`, `recovery-verification.json`, resource preservation audit.
Do not infer new-entry readiness solely from successful broker polling.

## Other workstreams

V6 incubator r5 through September 30 remains complete: 449 symbols, 40 members,
evaluated freeze at 02:32:01, 122 verified files. Updated freeze retained with
adverse return-MSE diagnostic recorded; no automatic model deployment.
Normal daily timer is restored. Selected config `deploy/incubator-continual-v6-r5.json`.
Clean one-session timing and sustained coexistence remain under OPS-INCUBATOR.PROOF/OPS.
V7 original discovery, frontier replay and MRHA migration continue. At 12:37,
migration had moved 431,970 files / 226,433,065,378 logical bytes. Replay counters
can reset on a new pass; inspect retained waves separately. Gate 7-3 remains open.

## Monitoring and constraints

Hourly watcher remains bound to this terminal; now includes Alpaca scanner/broker
receipts, service/timer observations and separate paper journal. Six watcher tests
and eight resource-sizing tests passed. Scheduled reports stay read-only.
Preserve frozen artifacts, old attempts, positions and journal history. No
paper/live model promotion, deadline weakening, or external messaging.
[Selected pointers](docs/CURRENT_STATE.md) · [Current tasks](TODO.md).
