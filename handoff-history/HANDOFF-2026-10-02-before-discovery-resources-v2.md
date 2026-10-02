# Handoff — October 1, 2026 — V6 paper quote recovery

## Selected user task

User needs reliable V6 Alpaca paper trading and viable prospective results.
The separate TLT input repair is complete. Quiet FLY quote intervals then caused
14:15/14:30/14:45 scans to abort before candidate computation. This session added
bounded concurrent monitoring recovery and deployed scanner v10.
Market-hours recovery is NOT yet verified: the session closed during the repair.
Keep OPS-PAPER.RELIABILITY open until prospective scans and reconciliation pass.
[Quote-recovery review](docs/reviews/2026-10-01-v6-paper-quote-recovery.md).

## What changed

New consumer: `scripts/run_v6_forward_resilient_v1.py`, derived from the verified
frozen scanner; feature/model/portfolio/provider modules still use frozen code.
Held monitoring runs beside full candidate computation, with its own session.
Only empty fresh-quote errors retry (two-second spacing, 120-second budget,
no later retry start than signal close +270s; existing request timeouts apply).
Allocation waits for successful monitoring. Permanent errors remain blocking.
Freshness stays 30 seconds; entry deadline stays five minutes. No model change.
Broker polling, actual-fill risk policy and order ladder remain unchanged.
The full-capacity shortcut is omitted; detection can run even if five slots remain.

## Deployment and evidence

Scanner: `healys-v6-alpaca-scanner.service`, v10 launcher and adapter.
New drop-in `95-monitor-v10.conf`; unchanged quarter-hour timer and v9 resources:
up to 11 memory-aware workers, 16 GiB maximum / 14 GiB high, numerical threads 1.
Paper manifest SHA:
`06459ec7cb58784cc35af07030c88f0685540a167074dd1c97fcb0a30e150f9c`.
Prior manifest/unit preserved under paper
`runtime-revisions/scanner-monitor-v10-20261001/`.
All prior manifest fields, admitted bridge files and frozen activation hashes
verified unchanged. New consumer files have their own admitted hashes.
Evidence root: `nn_meta/validation/v6-paper-quotes-20261001-r0/`.
At 15:32:54–15:32:57 Central, the installed scanner started/exited successfully:
449-symbol verification, unchanged model, idle/outside-market-hours.
Broker status at 15:34 was market_closed; scanner/orders timers remain enabled.
55 focused tests passed, plus real frozen-checkout import and syntax checks.
No manual orders, fake fills, replay deployment or historical position import.

## Next checks

Read paper `position-monitor-status.json` for attempts and terminal outcome,
then scanner status, elapsed time, candidates and actual broker reconciliation.
Hourly watcher includes the new receipt; it remains bound to this terminal.
A historical monitoring receipt or after-hours idle pass is not current health.
Observe market-hours recovery and entry-window timing next session. The repair
cannot guarantee provider freshness or successful trades; record real blockers.
Selected data remains the September 30 vintage-repair snapshot, SHA
`535dde7c63a7bc226a9f34b21b0cda18b8cf051128bbf7611e54b163ab825441`.
The scheduled producer owns the next daily snapshot; inspect its actual receipt.

## Other workstreams and constraints

V6 incubator r5 through September 30 remains frozen: 449 symbols, 40 members,
evaluation/final seal at 02:32:01. Adverse diagnostic retained; no deployment.
V7 discovery/replay and MRHA migration continue; this session did not alter them.
Daily after-close incubator and restoration remain under existing controllers.
Preserve all checkpoints, frozen artifacts, positions and journal history.
Do not infer trading readiness from incubator completion or broker polling alone.
[Current pointers](docs/CURRENT_STATE.md) · [Tasks](TODO.md).
