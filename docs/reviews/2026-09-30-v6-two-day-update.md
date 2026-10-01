# V6 September 29–30 daily-update measurement

The user requested immediate completion through September 30 after the initial
September 28 freeze, and a measured two-session update rather than another
initial catch-up. Preserve all prior artifacts and record diagnostic regressions.

## Discovered daily-transition defect

Restoring the persistent daily timer triggered an r3 September 30 run at 22:40:49
Central. Its refreshed snapshot included provider revisions to already consumed
stock history. At inspection the run reported many explicit history mismatch
failures. It was stopped, along with its retry timer, before recovery preparation;
all completed/partial r3 artifacts remain. This failed attempt is not a completed
update or a valid steady-state speed measurement.

The full snapshot comparison found 343 symbols with revised historical raw
cells: 432 volume, two open, two high, one low and one close. No old frozen values
are silently replaced. The new append-only snapshot preserves the exact frozen
September 28 prefix and appends 23,087 later raw bars. SATS, SAVA, SWTX, WBA and X
have no later bars in the source snapshot; retain their frozen-universe coverage.
Each symbol/adjustment has an audit under the new snapshot's revision-audit.json.

## Versioned recovery

Root/config: `incubator/continual-v6/r4/`, `deploy/incubator-continual-v6-r4.json`.
`incubator/daily_v6/snapshot.py` implements frozen-prefix extension; future dates
use the preceding completed daily snapshot. Provider revisions remain separately
observable. `inheritance.py` references verified r3 seals and the original r2
ancestry without relabeling either. The daily builder reuses unchanged frozen
proposal/feature routines, reconciles old and new candidates, and matures pending
labels. It retains exact occurrence identities and checks candidate continuity.

`run_v6_continual_v4.py` keeps fixed-family training and temporal validation,
records stage start times, and compares against the preceding completed update
(initially the September 28 candidate), irrespective of its diagnostic verdict.
The original base is unchanged; all matured extension rows enter the dataset
view. Newest validation-tail rows remain held out of weight fitting as before.

Daily service selection is a versioned drop-in, `40-daily-v4.conf`. Resources
remain the measured coexistence policy (20-GiB ceiling, autosized data workers,
two training threads, 400% CPU quota). V7/migration continue. Original 08:00
Central cutoff and data/provider failures remain effective; no partial freeze.

## Verification and measurements

Focused prefix preservation, ancestor seal/occurrence binding, existing proposal
semantics, scheduling and watcher checks passed. Original r3 source hashes remain
unchanged. Full parent-seal verification and a real-symbol preflight precede
launch; actual launch and update measurements must be recorded from receipts.

Timing scope must separate preparation/recovery cost, daily data reconciliation,
array preparation, training, evaluation/freeze and total elapsed time. This is a
two-session extension with competing workloads, not yet a proven daily SLA.

At 23:03:10 the isolated ADBE pilot completed in 120.27s: 720 candidates, 379
matured, 204 pending, 137 unfilled, 85 new feature rows, zero errors. The full
231,323-parent-seal census passed. Prior completed candidate seal remains
`4da950595e68f1db0d68431e85a1bbca22f8345c5472fae2dcaabe722e5f16d2`.

Full run started **23:04:36 Central**, three autosized data workers/two training
threads, 20-GiB limit, CPU 400%. Installed daily drop-in and restored timer were
verified. Full/pilot source contract matches
`d949483533d06d804cce36a2ab02c226e138758a670e2f8fdb298f9c323b613f`.
No full-update completion or daily SLA is claimed from this launch.

## User-requested dedicated allocation

The user requested the same compute used by the prior full run. A separate
operational wrapper preserves r4 frozen sources and checkpoints, pauses competing
batch services/timers using the established handover mechanism, then resumes the
same September 30 invocation. Shared autosizing is capped by the prior selected
five workers, at 3584 MiB per worker plus 4096 MiB host/2048 MiB parent reserve.
A temporary runtime drop-in selects 25/26-GiB high/max, no CPU quota, 16 available
training threads and 512 tasks. The existing daily service/viewer identity stays.

The completion path verifies the candidate, removes the exact temporary override,
and restores saved jobs/timers. Failure preserves checkpoints and leaves the
pause visible for review. Source/snapshot preflight and 12 resource/handover tests
passed. The initial 3-worker/2-thread interval and handover delay must be reported
separately from the dedicated interval in the eventual timing result.

Actual dedicated restart: **23:18:23 Central**, five selected data workers and
16 training threads. Host unit readback established MemoryHigh=25 GiB,
MemoryMax=26 GiB and CPU quota=infinity. All **32** completed symbol seal hashes
remained unchanged; five fresh symbol updates appeared at 23:18:50. No new V6
errors. The frozen launcher's preliminary autosize banner says three workers,
but final command overrides, resources receipt and five fresh symbols establish
that the dedicated selection is five.

Pause caveat: V7 discovery stopped cleanly; frontier exceeded its three-minute
stop timeout and was SIGKILLed at 23:17:02. Saved controller/capture receipts
remain, but this is not a clean frontier checkpoint claim; inspect its recovery
when restored. `dedicated/frontier-stop.log` retains the journal evidence.
Migration checkpointed at 268,618 files / 202,885,222,673 logical bytes with no
recorded error. Dedicated receipts preserve the stopped V6 invocation, all
completed seals, resource plan, pause plan and restart evidence.
