# V7 overnight resume without an overall cutoff — September 29, 2026

The user requested restarting V7, then explicitly instructed: “dont put a time
limit on it i want it to finish while i sleep.” Continue the selected finite
pending replay queue until completion, with no overall wall-clock cutoff.
[Preflight and dated progress](2026-09-29-v7-overnight-resume.json).

The prior evening supervisor exited successfully at 22:01 Central after its
scheduled two-hour pending replay and 30-minute original discovery passes.
The sealed frontier capture already completed all 109,825 windows at 19:30.
No recapture or new input epoch is needed for this restart.

Before restarting, all eight campaign input anchors and each existing wave's
source declarations passed hashes. All 31 retained wave databases passed SQLite
quick checks under their exclusive locks. MRHA UUID 62C9-C390 was verified read/write.
Preserved checkpoint: 59,278 cohorts / 5,021,957 horizon-target evaluations, ten
completed securities; earlier progress/declaration copied to
`nn_meta/validation/v7-overnight-resume-20260929-r0/`. Source-bound controller,
worker, quote/reference indexes, exclusions and plan remain unchanged.

`healys-v7-pending-overnight-20260929.service` started at **23:28:20 Central**,
resuming the same `v7-pending-replay-campaign-20260929-20260929T233047Z` directory.
Its original four-hour slice remains running to avoid interrupting active work.
The subsequently authorized `healys-v7-until-complete-20260929.service` waits
for that exact unit to exit, then repeatedly resumes the same bound campaign
until `replayed_pending` reconciles all 93 securities. There is **no overall
cutoff**: four-hour controller checkpoints are automatically continued, not a
request to stop overnight. Memory/disk pressure waits and retries when capacity
returns; integrity/process failures remain explicit rather than blindly retried.

Supervisor state: `nn_meta/validation/v7-until-complete-20260929-r0/`:
`binding.json`, `progress.json`. Running campaign state remains in its original
root, selected by `v7-evening-continuation-20260929-r0/selected-replay.json`.
A controller's completed-security counter rebuilds during each traversal; its
initial zero does not erase ten retained completed wave receipts.

Both execution services use one autosized worker, CPU 100%, 3/4-GiB memory
high/max, no swap and Nice 15. The waiting supervisor does not start an overlapping
worker. Existing 6-GiB available-memory and 20-GB local-disk guards remain.
V6 and the low-priority MRHA migration continue independently; no source contracts
or training schedules were changed. A temporary read-only sandbox mount view
required host-side mount verification; MRHA itself was healthy.

Fresh progress exceeded the retained 5,021,957 evaluations after restart, with
no reported worker failures. Launcher syntax checks and the focused continuation
state-transition test passed. That test checks continuation, truthful full-count
completion and refusal to mask failures/stale-running receipts. No unrelated
training or broad regression suite was rerun for this operational restart.

The completion target is this frozen **21,624,449 horizon-target replay queue**.
Its output may identify further missing inputs. Finishing it does not establish
full V7 execution coverage, close gate 7-3 or imply V7 training has completed.
No guarantee is made that the remaining work will fit into one night.
