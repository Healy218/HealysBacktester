# V7-3 performance pause and redesign — October 2, 2026

## User direction and observed stop

The user requested pausing V7 and rethinking optimization because current
throughput implies weeks. This supersedes the previous no-cutoff continuation
instruction. Neither original discovery nor frontier capture/replay may resume
without a new user instruction. Existing V6 paper/daily incubator schedules and
other services are unchanged. Hourly watcher remains active; V7 inactivity is
intentional and must not be diagnosed as a stall or automatically restarted.

Discovery stopped at 09:59:06 Central, frontier at 09:59:13. Both supervisors
reported stopped; both child campaigns reported checkpointed with no failures.
Both service cgroups disappeared. Original/recovery/supervisor/current replay
locks were successfully acquired read-only and released during verification.
Pause evidence: `nn_meta/validation/v7-performance-pause-20261002-r0/pause.json`.
No frozen producer, input, wave declaration or scientific output was edited.
Stop preserves committed SQLite cohorts; any uncommitted interrupted cohort may
need replay. Interrupted wave receipts are not evidence of lost committed work.

Retained at 10:02 Central: original discovery 1,534,496 cohorts / 143,947,955
horizon-target assessments; 60 finished waves, seven empty-demand cases and 133
partial waves. Current replay 47/93 securities, 172,783 cohorts / 14,520,464
assessments. Earlier 93-security replay remains complete and separate.

## Established facts versus hypotheses

The full frozen plan has 591 job reports and 328,386,847 distinct horizons, each
with five targets: 1,641,934,235 horizon-target assessments. All 60 finished-wave
counts agree with their corresponding per-job denominators. Assessment counts
include pending-input outcomes; they are not all finalized training labels.

The 22:00–08:00 log comparison found about 271,599 additional cohorts and
26,790,800 additional assessments across 134 matched securities. Nine securities
without a pre-window log baseline were excluded. Receipt endpoints approximate
clock boundaries. Extrapolating that workload mix unchanged gives approximately
23 days for remaining original discovery, excluding successor capture/replay.
This is a rough baseline, not an ETA promise.
Evidence: `logs/lab-hourly-watch/discovery-throughput-20261002.json`.

Code/query inspection found concrete optimization candidates:

- Five-minute process slices repeatedly initialize/verify inputs and readers.
- Discovery reads the ordered jobs table from the beginning and checks completed
  cohort keys while walking it. EXPLAIN reports SCAN jobs. The existing primary
  key can support a seek on (symbol, decision_ns); a correct side-aware cursor
  must handle both option sides, cohort atomicity and inherited checkpoints.
- Replay fetches selected source cohort rows before checking whether that cohort
  is already completed. Filter completed keys before fetching frozen source rows.
- Every 15 seconds, progress recomputes grouped sums over buckets. EXPLAIN on a
  retained 161,525,760-byte wave database reports SCAN buckets plus a temporary
  B-tree for GROUP BY. Transactional incremental counters could avoid this scan.
- The producer commits each cohort with SQLite synchronous=FULL, and serializes
  membership/results. Quote readers use a two-pack cache and check immutable
  payloads. Existing prefix/horizon sharing is already implemented; do not
  propose it as a missing feature or remove integrity checks to claim speed.

These observations establish operations performed, not their percentage of total
runtime. Their actual cost must be profiled before selecting the main rewrite.
The overnight run still used two workers. Four-worker throughput is unmeasured.

## Recommended bounded work

1. Freeze a small representative benchmark manifest referencing retained inputs:
   small finished case, large partially completed case and an I/O-heavy case.
   Copy working checkpoints into a new validation revision (including required
   SQLite recovery sidecars); never profile by advancing the selected campaign.
   Separate discovery and pending replay. Record exact cohort memberships and
   cold/warm and first/resumed conditions. Keep the benchmark bounded.
2. Profile time in startup/hashing, completed-prefix traversal, core execution,
   quote decode/cache misses, progress reporting, serialization and database
   commits. Measure useful cohorts/assessments per second, I/O bytes, RSS and
   restart latency, under representative V6 coexistence.
3. Implement the highest-impact measured changes in a new source-bound revision.
   Likely first candidates: persistent workers with periodic durable checkpoints,
   indexed resume cursors, skipping completed replay keys before loading rows,
   transactional incremental reporting, and bounded writes/caches. Preserve
   provenance, outcome semantics, exact membership and crash recovery.
4. Compare old/new on the SAME frozen cohort set and inherited checkpoints:
   exact pending requests, membership, exclusions, execution outcomes and inputs;
   kill/resume parity and bounded memory/disk. Speed alone cannot pass.
5. Only then benchmark worker scaling and re-estimate full-scope runtime. If a
   meaningful reduction still requires additional hardware or a representation
   change, present that measured tradeoff before broad execution. Report measured
   speedup and uncertainty; no invented 5x/10x promise or new gate closure.

V7 stays paused for this analysis. This document is a plan and inspection record,
not completed optimization, a profiling result, or permission to resume.
