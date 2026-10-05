# January demand study — elapsed-time continuation

The initial [study](ETFE_DEMAND_20261004.md) reached its one-hour wall-clock
ceiling during interactive approval waits. At October 4 23:58 UTC it had made
256 successful GETs and one failed sandbox attempt, with two 128-request live
runs totaling about 254 seconds and 256/378 new discovery partitions complete.
The second live invocation began after the initial wall deadline; this is a
recorded orchestration deviation, not evidence that the original time ceiling
was enforced. Raw requests, source snapshots and plans remain unchanged.

The user's continuing acquisition instruction authorizes completing this bounded
work. This successor changes only the study's aggregate time accounting to a
maximum of **one hour of active capture time**, summed from all capture run
receipts (including earlier attempts), excluding approval/idle/analysis waits.
Each invocation retains the engine-enforced 30-minute wall-clock cap. Before
each continuation invoke, inspect cumulative calls, elapsed capture time and
root bytes. Do not reinterpret or replace the original study's observations.

All other ceilings remain: at most four invocations per discovery/boundary/
surface root (including failed calls), 128 GETs/invocation, 512 MiB/raw root,
32 MiB/page, serial 60 GET/minute, and 1,536 total GETs. Only one discovery
invocation remains after the sandbox call and two live batches. Preserve the
same dates, contracts, context scope and no-training/admission boundary.
`CONTINUATION.json` binds this revision, the initial inventory/plan and the
existing run-receipt hashes; subsequent runs stay ordinary immutable run receipts.
