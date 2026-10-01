# V6 paper input-vintage recovery — October 1, 2026

User authorized repairing V6 so Alpaca paper trading can continue today.
Scans from 08:45 Central failed with `TLT: all price vintage changed` during
bar refresh. Broker polling continued. The 09:45 scan also recorded a missing
fresh PYPL option quote. These were paper-runtime issues, separate from the
completed r5 incubator freeze; no new model was deployed.

## Repair and preservation

Published **10:45:53 Central**: `nn_meta/live/v6_server/data/2026-09-30-vintage-20261001-r1/`,
manifest SHA `535dde7c63a7bc226a9f34b21b0cda18b8cf051128bbf7611e54b163ab825441`.
All 449 symbol inputs validated; fresh raw/adjusted overlap passed for 444
currently available symbols. The five previously unavailable symbols remain
accounted for. TLT alone required a new full adjusted history (39,780 provider
rows before session filtering). The 26 sealed option daily captures were reused.

The prior September 30 manifest still hashes to
`39ea277fa6b80eb50941023c96f7cee8558faa7130a536f6b2a42f84cb612b29`.
Activation, model/release and original data remain unchanged. The later
resource-only paper manifest revision retains the original trading-policy bindings. Journals/positions were not reset; normal broker automation continued.
The frozen producer and scanner guards were not modified.

The initial broad rebuild started 10:01 and was stopped after prolonged network
waiting. Its partial output and attempt are preserved. The incremental repair
started 10:22:54, using the verified September 30 histories as the producer's seed.
An independent exact round-trip comparison checked **7,167,256 rows each raw and
adjusted across all 449 symbols**. The first incremental surface build correctly
rejected 696 missing historical option-root spot keys; the seed was corrected to
retain the original historical daily raw alias history. At 10:42:56 the resumed
build reused all 898 stock files, rebuilt context, and validated at 10:45:05.
Neither failed attempt was published or weakened a validation guard.

Helpers: `scripts/repair_v6_paper_vintage_20261001.py` and
`scripts/repair_v6_paper_incremental_20261001.py`. Evidence root:
`nn_meta/validation/v6-paper-vintage-20261001-r0/incremental/` contains seed
provenance/round-trip audit, captured verification queries, validation, publication,
preservation audit, failed-attempt record and observed paper exit receipts.
The original broad attempt is in the parent evidence directory. Build services
used 12 GiB hard / 10 GiB high memory limits and two CPU equivalents. V7 and
migration continued. Those limits did not change the existing scanner policy.

## Market-hours verification

The manual retry started 10:45:53, passed bar refresh and detected 61 signals
across 53 symbols: 444 symbol results, zero detection errors. It then rejected
new entries at 277.995 seconds because the late start had passed the five-minute
signal-close deadline. Late entries were not forced or replayed. The normal
11:00 scan completed at 11:05:05 in 299.750 seconds with 356 candidates and zero
detection errors, but its UUUU broker entry missed the broker window. Later 11:15,
11:30 and 12:00 scans recorded results; an actual UAL entry filled at 11:20:39
(10 contracts at $7.30), then closed at 12:07:04 (10 at $6.15). Scans at 11:45
and 12:15 withheld new entries on missing fresh UAL quotes. The 12:30 pass took
345.372 seconds and missed the signal-close deadline. Thus input repair resumed
actual trading, but eight-worker timing had insufficient margin under shared load.

During the recovered exit-monitor phase, the existing PYPL strategy exit was
recorded and Alpaca filled **13 + 11 contracts at $2.62**, at 10:46:32 and 10:47:02.
The subsequent broker poll reported zero positions. These are actual paper fills,
not simulated projections or an asserted new-entry recovery.

## Scanner timing follow-up

A new v9 launcher uses the shared autosizer (1,280 MiB per worker, 8 GiB host
reserve, 2 GiB parent reserve) within a 16 GiB service limit: presently 11 workers,
each with one numerical thread. Memory-high is 14 GiB; swap remains disabled.
The unchanged v8 adapter retains source reconciliation, deterministic ordering,
frozen model, quote checks and both deadlines. The installer waited for the
active scanner lock, backed up the previous manifest/unit, and admitted only the
new launcher hash plus a resource-policy label. No active scan or broker was stopped.
Current manifest: `216d61365a3b65c5eccce28e5fe1da9eb408bebd2dc18c0eb47f3241aa77b890`.
Evidence: parent repair directory `scanner-resources-v9.json`, `pre-v9-scans.json`,
`observed-resumed-orders.json`; saved deployment under the paper state
`runtime-revisions/scanner-resources-v9-20261001/`. V9 completed the 12:45, 13:00,
13:30, 13:45 and 14:00 scans in **261–286 seconds**, zero detection errors.
The 13:15 invocation began late (13:15:38) and correctly rejected a missed deadline
after 263.869 seconds; worker count alone does not guarantee every deadline.
Alpaca subsequently filled **26 FLY puts at $3.20 at 14:06:47**, after two canceled
steps. The 14:15/14:30/14:45 scanner passes withheld new entries because Massive had no
fresh FLY option quote. An Alpaca stale-quote broker failure at 14:38 recovered by
14:39; another stale-quote poll occurred at 14:42, and polling succeeded again
at 14:46. The held account position remains 26 FLY puts. No freshness guard was
relaxed. **Remaining blocker:** new-entry scanning is paused until a valid fresh
Massive quote for the held FLY contract is available. Data and timing repairs
and actual trading resumption are verified; uninterrupted current operation is not. `v9-scans.json` and
`recovery-verification.json` retain the measured outcomes.
Eight resource-sizing tests passed, including
low-memory reduction and independence from inherited numerical-thread settings.

The existing hourly watcher now includes Alpaca scanner/broker services,
independent receipt summaries and a separate paper journal. Six focused watcher
tests passed, including a successful broker poll paired with a failed scanner.
Watching remains read-only; no schedule, trading guard or model selection changed.

[Current state](../CURRENT_STATE.md) · [Operating procedures](../../DOCUMENTATION.md#operations-and-recovery)
