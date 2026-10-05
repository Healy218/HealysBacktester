# ETFE bounded phase-B trade acquisition

Consume only the completed, independently audited causal component pilot at
`nn_meta/validation/etfe-causal-20261004-r0`. Its GLOBAL_DEMAND contains 225
uncaptured option-trade intervals, 68 contracts and 4,626 contract-minutes on
January 19, 2024. Preserve every logical event membership through the bound
parent demand; this does not expand to holding/roll/execution demand.

Group identical start/end intervals, with at most 100 symbols per query. The
selected inventory produces 103 queries. Do not widen intervals or infer option
hours. Use historical option trades, no feed parameter, limit 10,000, ascending
order, complete pagination and inclusive provider end = exclusive end minus 1 ns.
Keep every response occurrence, missing IDs, conditions and native timestamps.
No current contract metadata is imported as historical eligibility.

New immutable raw root, existing bounded capture engine, new source-bound
orchestrator and parent hashes. Preserve the completed pilot, normalization and
acquisition sources without modification. Verify the parent demand and source
bindings before every run. One serial stream, at most 60 GETs/minute and 128 GETs
per invocation. Total study: 512 GETs including failures/retries, 8 invocations,
30 minutes accumulated active capture time excluding idle/approval waits. Raw
root cap 512 MiB including failures and source copies; page cap 32 MiB. Existing
disk/RAM reserves and provider retry/wait policy apply. Stop at limits; a failed
forecast never silently increases the budget. The normalized successor retains
its own existing 2-GiB root and resource checks. No parallel workers.

Before capture, report measured prior fresh trade density and raw-row byte size,
with median/p95/maximum density scenarios for all demanded contract-minutes.
These are scenarios rather than promised completion estimates. Actual receipt
sizes, row counts, requests, active time and peak RSS determine completion.

Prove a real bounded stop/resume with unchanged committed page/body hashes.
Require every query to terminate, normalize through the existing typed reader,
and independently reconcile the ordered raw occurrence sequence for every
partition. Independently reconcile all 225 symbol/interval edges to transport
queries, every returned row to the correct half-open interval, and the original
logical membership bindings. Preserve empty intervals as unresolved absence.

Produce a 4,626-row demanded-minute census, including minutes without observed
trades and availability of previously captured bars. Record raw observed counts,
volume, condition counts, missing/native repeated IDs and duplicates; do not
silently deduplicate or turn captured absence into a valid zero-trade model
feature. No signed trade feature without defined equal-time ordering. Bar/trade
price and volume comparisons, if reported, are diagnostics under explicit
condition policy, not proof of publication timing or execution eligibility.

This closes only ETFE-1.trade-window-capture. Dated conditions/provenance,
regular option hours, historical listing/terms/action evidence, out-of-stock-RTH
feature windows, full-window phase-B/C demand, final feature schema and integrated
ETFE-4.pilot remain open. No execution, model-ready dataset or training is run.
