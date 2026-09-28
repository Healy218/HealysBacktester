# Handoff — September 28, 2026 — V6 paper operational; return to 7-3

## Focus and stopping point

The user prioritized V6 paper readiness before returning to gate 7-3. Repaired
provider-restated VOO inputs, process sizing and an intraday research-start hole.
The 10:30 Central scan completed in 243.058 seconds with 281 candidates and no
processing errors. One actual Alpaca paper order was accepted, canceled unfilled
and reconciled. First actual fill remains pending; no model performance claim.
[Readiness evidence](docs/reviews/2026-09-28-v6-paper-readiness.md).

## Completed and preserved

- New immutable input snapshot `2026-09-25-vintage-20260928` published after all
  449 symbols validated; 23 existing option-context captures reused. Original
  snapshot, frozen 40-member model and paper-account activation remain intact.
- Scanner v3 autosizes up to eight workers within 12 GiB; measured peak about
  7 GiB. Each numerical worker remains single-threaded. Prior launcher/activation
  versions retained; scanner, broker, monitor and data schedules remain enabled.
- Broker cancellation/reconciliation worked without synthetic fills. Simulated
  scanner entries and actual broker holdings remain distinct. A second source
  entry missed the broker window and was correctly withheld.
- Research catch-up stopped during paper hours, checkpoints retained. A tested
  calendar condition rejects delayed intraday starts; no old freeze relabeled.
- 21 focused tests plus shell/systemd validation passed. Runtime/model hashes
  reverified, fresh account GET confirmed eligibility, no positions/open orders
  at the final account check. Subsequent actual health belongs to live receipts.
- V7 entry download completed at 04:58; automatic V6 handoff worked at 05:00.
  Its final range count reconciled. Overall gate 7-3 remains open.

## Next actions

1. Read TODO, then use [CURRENT_STATE](docs/CURRENT_STATE.md) for exact paper,
   research and V7 pointers. Do not repeat activation or reset broker journals.
2. Return to remaining 7-3 references, actual held/exit/roll/stock gaps and
   reconciliation. Preserve the partial 7-4 ledger. Entry capture is complete;
   do not rebuild the catalog, daily data, demand census or packing trial.
3. Observe the first actual prospective paper fill and sustained session behavior.
   A successful scan/accepted order is not a fill or a trading-performance verdict.
4. Incubator r1 still needs full catch-up and training. Restated stock inputs now
   require an explicit compatible/new lineage review; do not force old feature
   seals to accept changed history. Full nightly latency remains unmeasured.
5. Retain the October 2 provider decision and existing FA collection schedules.

## Constraints

Preserve unrelated dirty/untracked work. Source-bound research, operational
models and broker state stay isolated. A new input/model version does not itself
promote a model. Full-scope validation, deployment and measured outcomes remain
separate. The research diagnostic tail is not an untouched performance test.
