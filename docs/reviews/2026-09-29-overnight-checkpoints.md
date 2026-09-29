# September 29 overnight checkpoints — session close

Dated observation: September 29, 2026, 07:33 Central. Service/journal checks
were made in the immediately preceding status check; receipt copies and their
hashes are retained in the [observation](2026-09-29-overnight-checkpoint-observation.json).
No services were restarted or resource limits changed for this documentation update.

## V6 research update

The r3 build was executing, with 90/449 symbols complete and zero recorded errors.
All 17 formerly failing symbols now have complete full-symbol inventories, beyond
the earlier exact-prefix verification. Training has not started; no latest-candidate
pointer exists. Existing model/paper deployment remains unchanged.

The two-worker update has not completed its initial catch-up overnight. Full freeze
and next-trading-day latency are still unproven. Its existing calendar-aware deadline
is capped at the next open minus 30 minutes; inspect subsequent status/service-exit
receipts before resuming, because the market-hours start guard also remains active.
The unfinished September 28 date and original snapshot stay pinned across retries.

Selected config/root remain `deploy/incubator-continual-v6-r3.json` and
`incubator/continual-v6/r3/`. The prior [repair evidence](2026-09-28-v6-continual-error-repair.md)
and immutable base/r1/r2 checkpoints remain valid.

## V7 queue and discovery

The full execution planner stopped normally at its eight-hour budget at 05:13:43
Central, leaving a resumable checkpoint: 582/591 securities, 789,797,718 original
proposals reconciled and 326,962,118 distinct horizons. Nine securities remain;
one already has 144 source batches checkpointed. This is queue preparation,
not completed option-path evidence.

Discovery stopped earlier, at 05:08:48 Central, with exit status 1/FAILURE:
`ValueError: Execution working-store allocation reached`. The controller enforces
20,000,000,000 bytes of generated state and a separate 20-GB free-space floor.
The stop was the generated-state allocation, not memory exhaustion or a full disk;
90.03 GB local free was observed at the snapshot. The journal records 6h35m wall
time and 5G peak memory. Preserve all results before choosing a storage repair.

Per-wave receipts contain 30,462,620 horizon/target dispositions across 93 started
securities: 25 discovered, 66 checkpointed and two interrupted with stale running
flags. They record 112,112 pending requests summed across securities (not globally
deduplicated). Neither discovered nor an observed no-contract/unfilled disposition
means a completed numerical training label. Further actual input capture/replay
rounds remain required.

Two other securities failed while building their quote indexes:
`BBG000BCQ6J8` and `BBG000BF8TF5`, both with
`No completed capture packs for selected security`. Diagnose against their frozen
selection/demand census before deciding whether these are valid empty universes
or missing coverage. This error alone does not invalidate completed entry capture.

The parent progress file still says running and names active securities, although
the service is stopped. A collected transient unit's default success fields do
not override the retained failure journal. A recovery should publish truthful
terminal state as well as address the storage and empty-index paths.

## Evidence boundaries

Gate 7-3 stays open. Gates 7-1/7-2, full entry capture and known reference exception
adjudication stay complete. No admission rules or scope changed. The approved
10,831 exact pairs, 22 rename corrections, stopped parity pilots and five-path
integrated ledger remain retained evidence. Use CURRENT_STATE for exact pointers
and TODO for actionable continuation; this review does not authorize a new campaign.
