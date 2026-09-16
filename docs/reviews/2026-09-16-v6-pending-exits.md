# V6 September 16 recurring error: pending exits and observed recovery

Read-only diagnosis during the V7 readiness continuation. No activated runtime,
model, timer, quote-age rule, portfolio state or alert settings were changed.
No test notice was sent.

## What failed

The 11 quarter-hour passes from 13:45 through 16:15 UTC failed with
`ValueError: unresolved position monitoring; new entries withheld`.
Saved `exit_errors` identify `ValueError: no fresh post-decision option quote`:
DUOL in all 11 passes and FXI in the first three. Evidence extracted from the
actual service journal is in
`nn_meta/validation/v6-incident-20260916/producer-statuses.json`.

Daily inputs were current through September 15; refresh passed at 12:00 UTC.
This is distinct from the earlier missing-provider-file/stale-context outage.
The premarket passes were idle; the observed September 16 first actionable pass
failed. The user's report that the morning looked healthy may refer to those
idle statuses; the available evidence does not establish an earlier successful
market pass that day.

The frozen implementation queries only quotes within the preceding 30 seconds,
after the exit trigger. A missing quote leaves the position pending and blocks
new allocation. The normal producer retries only once each quarter hour.
Thus quotes between those brief polls can be missed. Missing fresh responses are
proved by the error path; sparse underlying quote updates versus provider timing
was not independently reconstructed, so neither is claimed as the sole cause.

## Actual exits and recovery

Saved affected position records:
`nn_meta/validation/v6-incident-20260916/affected-positions.json`.

- FXI261030C00034500: trigger September 15 13:45 UTC; completed sale September 16
  quote received 14:30:29.724862 UTC at bid $0.85, ask $0.92, sizes 9/17.
- DUOL261030C00148000: trigger September 15 14:45 UTC; completed sale September 16
  quote received 16:30:37.834336 UTC at bid $11.10, ask $13.70, sizes 14/13.

Both position records now say closed. These are paper bid executions under the
existing fractional convention, not broker fills. Their retained trigger times
show why the failure continued across days.

The 16:30, 16:45, 17:00 and 17:15 UTC producer passes completed. The first three
were 213.171, 203.728 and 204.260 seconds; the fourth was 212.481 seconds.
The latest inspected portfolio held three open positions with six closed and
29 completed allocation cycles. The home relay exported 15 event files.
Independent read-only SSH inspection found server health `healthy` at
17:27:51.261060 UTC, expected close 17:15 UTC, and the corresponding completed
relayed producer status. Production `.alert_batches.sqlite3` contained **15 sent
V6 notices and zero pending**. Recovery was observed; no permanent fix is claimed.

## Follow-up

Preserve these receipts and the failed passes. If pending exits recur, inspect
the exact contract, quote window and last provider observation. A separate,
bounded pending-exit retry path could reduce missed quote opportunities without
weakening the 30-second age guard. That would require runtime regression tests,
revalidation and deployment of a new activation; it was not implemented here.
Do not suppress the operating notices or assume every future pass will succeed.

## SEDG explanation and user direction

SEDG opened at 17:03:30 UTC and exited at 17:30:32 UTC, approximately 27
minutes later. Both records show ask $3.90 / bid $3.15: a 21.2766% full spread
relative to the $3.525 midpoint. The recorded return after existing costs is
−19.4727%. This option loss did not trigger the exit. The deployed 5% stop
uses the underlying stock, not option quote P&L. The BBW short exit crossed
when the 17:15–17:30 bar closed at $34.56 above its $34.53225 basis. Entry
stock price was $34.33; the approximate 5% short stop was $36.0465 and
subsequent high only $34.70. Evidence: `nn_meta/validation/v6-incident-20260916/`
`sedg-positions.json` and `sedg-exit-diagnosis.json`.

After this explanation the user directed: leave the V6 experiment as it is
and continue getting V7 ready. Tentative unshipped spread-policy changes were
removed. No new spread cap, midpoint fill/stop policy, or V6 deployment was
adopted. Further V6 investigation is not the next task.
