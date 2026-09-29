# Post-outage paper reconciliation and V6 restart — September 29

The user selected steps 1–2: reconcile Alpaca paper and resume V6 catch-up. V7
steps 3–4 remain deferred. [Receipts](2026-09-29-paper-reconciliation-v6-resume.json).

## Paper account — reconciled

The installed runtime's authenticated `check` passed at 17:27 Central. Independent
read-only broker queries at 17:30 verified the expected account fingerprint and
compared all **48 broker orders** since activation against all 48 journal orders:
contract, status, filled quantity and fill price matched. **Zero open orders**.
The runtime check's `orders: 48` counts journal records, not outstanding orders.
Eight orders filled: five entries and three closes. Actual holdings equal net
broker fills exactly: AXP261106P00305000 ×7, QCOM261106P00185000 ×5,
SMCI261106P00041000 ×18, VG261030P00012500 ×104. QUBT's 117-contract entry
was fully offset by its three closes (27+65+25). No unknown positions, ambiguous
orders or discrepancies were found. No orders were submitted or canceled here.

This completes the first prospective actual-order/fill reconciliation observation
(OPS-PAPER). It does not establish uninterrupted intraday risk monitoring: the
computer was unavailable during part of the session. AXP's after-hours broker mark
was 10.35 versus 12.15 average entry (-14.815%), below the configured 12.5% stop.
That account mark is not a fresh tradable quote or a retrospectively observed stop
trigger. Existing runtime checks fresh OPRA quotes when the market opens and gives
risk exits priority. No stop was manufactured from stale after-hours prices.
Orders/monitor timers remain enabled for 08:00 Central September 30; scanner
08:00:05. They retain market-clock guards; regular trading starts 08:30 Central.
Observe fresh risk handling, particularly AXP, at the next session.

Before reconciliation, broker/portfolio databases were backed up through SQLite
and prior receipts retained under `nn_meta/validation/v6-post-outage-resume-20260929/before/`.
Full read-only order audit and its exact script are beside that directory.

## V6 — resumed and advancing

Verified **all 74 source hashes**, dependency/Python runtime identity, the pinned
September 28 snapshot hash and **all 95 completed symbol receipts**. No source or
frozen contract changed. Installed service retains CPU 400%, 19/20-GiB high/max,
no swap, autosized data workers (ceiling four), two training threads, 12-hour
invocation budget and calendar deadline. V6 data producer and V7 discovery/capture
were inactive. Both research-window and completed-entry conditions passed.

Started `healys-v6-continual.service` at **17:31:19 Central**. Actual final process
arguments select **three data workers / two training threads**, overriding the
frozen launcher's earlier default two-worker arguments. This is a long-running
oneshot: `activating/start` with a live MainPID is expected while research runs.
The new receipt binds the same `e909f7d...` contract and September 28 snapshot.
By 17:33 inspection it had advanced to **96/449**, zero reported errors, and fresh
COIN/CONL/COP progress. Peak memory observed: 3,080,073,216 bytes (~2.87 GiB).
This is startup/progress evidence, not a complete catch-up, training or freeze proof.

Internal free space remains approximately **87 GiB**; MRHA about **693 GiB**.
V6's existing data builder checks a **12-GB reserve** before symbol/candidate work.
MRHA stays mounted. No payloads or Steam files were moved, deleted or modified.
Keep capacity under observation as the catch-up grows; no storage guard was relaxed.

Next: observe catch-up/termination receipts and next-session paper risk checks.
V7 remains at the verified power-interruption checkpoint; no V7 service started.
