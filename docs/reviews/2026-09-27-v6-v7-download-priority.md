# V7 download priority — September 27, 2026

The user requested deferring V6 continual research while V7 downloads. V6 was
stopped and its timer temporarily disabled; completed artifacts were verified
before installing a completion condition and restoring its normal timer.

The 20:18 Central hold receipt verified **273 completed feature batches and
1,628 completed outcome records**. These include unfilled outcomes and are not
counts of trading fills. Mutable run status now says `waiting_for_v7_entry_download`;
`incubator/continual-v6/r1/upstream-hold.json` retains the prior status. No completed
freeze or checkpoint was changed. Incomplete work can be recomputed on resume.

The service now checks the selected V7 meter for the expected campaign identity,
`entry_capture_complete`, `full_entry_coverage=true`, zero pending work and no
stop reason. Missing/invalid, interrupted or other-campaign receipts defer V6.
Seven targeted tests passed. Systemd condition validation and a real skip check
confirm that the timer can remain enabled while V6 research stays inactive.
The user confirmed the objective is to finish V6 before the next trading day if
time permits. Morning retries now run every 15 minutes from 04:00 through 07:45
Central, so V6 need not wait until the former 06:15 retry after an early finish.
After V7 finishes, the next scheduled attempt resumes V6, subject to its existing
daily-input condition and 08:00 Central cutoff. The initial catch-up plus roughly
two hours of member training makes tomorrow readiness uncertain; this change
improves the opportunity without promising completion.

At 20:11 Central, the V7 two-minute sample ran at 150.8 ranges/sec versus
268.6 over ten minutes. V6 had started at 19:59, so the periods overlap. But
response density also increased to 0.444 MB/range in that two-minute sample,
versus 0.165 over ten minutes. No causal slowdown attribution is established.

The original implementation/pilot evidence remains valid. V6 paper operation,
the daily input producer, and V7's running capture were not changed.
[Current pointers](../CURRENT_STATE.md) · [Tasks](../../TODO.md)
