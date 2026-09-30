# September 30 — V6 three-step paper policy and overnight progress

## Finding and user decision

The sell ladder was operating. September 30 journal evidence shows QCOM filled
on the third old step at $11.05; SMCI also closed. AXP tried $11.16, $10.87,
$10.59 and $10.30; VG tried $0.78, $0.76, $0.74 and $0.72. Both exhausted
unfilled around 08:50 Central. Their starting bids were $10.15 and $0.70;
old final limits did not reach those bids. Later market movement also matters.
Exhausted ladders do not automatically restart and previously disappeared from
routine poll outcomes. This was not absence of sell-side stepping.

The user selected fixed starting-midpoint multipliers: buy 1.05/1.10/1.125;
sell 0.95/0.90/0.875, with 30/30/60-second waits. They explicitly approved one
fresh ladder for each remaining AXP/VG exit. These are execution concessions,
not new stop-loss thresholds or compounded discounts. Mark/risk/model logic is
unchanged. A limit still need not fill: Alpaca paper matching uses current NBBO
([provider documentation](https://docs.alpaca.markets/us/docs/paper-trading)).

## Implementation and deployment

Code commit `4f9c02e` adds `v6_pricing_v4.py`, `v6_bridge_v4.py`,
`v6_step_slices_v2.py`, runtime dispatcher v5 and scanner adapter/launcher v7.
Policy is `midpoint-step-5-10-12.5pct-v4`. Existing source-bound versions remain
unchanged; in-flight old chains retain their original four prices and waits.
Sizing/reservations use the maximum buy limit. Cancel confirmation, remaining
quantities, displayed liquidity, ownership and dependency checks remain enforced.
Successful sell slices continue only against remaining broker-owned holdings.

The manifest admits exactly two old exhausted exit IDs for a single retry each.
Stable `|retry|midpoint-step-5-10-12.5pct-v4` IDs preserve all previous orders and
prevent duplicate submissions after restart. Failed retries cannot retry again.
The poll receipt now explicitly lists exhausted exits with remaining holdings.

82 targeted tests passed: new/legacy ladders, partial fills and cancellation
races, cash reserves, quote freshness, uncertain submissions, finite retries,
slicing, scanner source reconciliation and existing broker runtime checks.
Shell syntax and diff whitespace checks passed. No broad training/test campaign.

Deployed at **10:33:22 Central**. Timers were paused while locks drained;
zero open broker orders and zero active chains were required. Frozen sources,
account identity and prior-session daily inputs verified. SQLite backups passed
quick checks. Timers resumed; no manual test orders were manufactured. Normal
polling submitted the two user-approved retries.

Backups: paper state's `runtime-revisions/step-policy-v4-20260930/`.
Manifest SHA: `59b972e4c15daeca4f7951aca272a885eab275cd77b16570d0bcf560e24b61fe`.
Local deployment/observer evidence and the cutover script are under
`nn_meta/validation/v6-step-policy-v4-20260930/`.
[Retained deployment, fills and research observation](2026-09-30-v6-step-policy-v4.json).

## Actual paper results

At **10:40 Central**, authenticated broker/journal reconciliation covered all
77 orders with matching statuses and filled quantities; zero open orders.
Both retries filled at their second steps:

| Exit | Fresh anchor | Step limits | Actual fill |
| --- | --- | --- | --- |
| AXP ×7 | $10.675 | $10.14 / $9.60 / $9.34 | 7 at $9.75 |
| VG ×104 | $0.775 | $0.73 / $0.69 / $0.67 | 104 at $0.70 |

Both first steps canceled unfilled before the replacements were submitted.
Only WFC ×26 remained in the broker account at observation. These are paper
fills, not evidence of live execution quality or model profitability.
The 10:30 scanner failed before cutover because WFC had no fresh post-decision
option quote, withholding new entries. Broker polling continued successfully.
The 10:45 scan then failed on a newer, never-filled VG projection. The source
cleanup v2 incorrectly treated older fills in the same contract as fills belonging
to this new signal. Actual AXP/VG exits were already flat at the broker.

## Follow-up scanner repair

Commit `1bbe651` adds source reconciler v3 and scanner adapter/launcher v8.
Cleanup now distinguishes signal IDs. Before archiving a never-filled expired
signal it requires zero broker holdings, zero net contract fills in the journal,
terminal known contract orders, no fills in that signal, and no active chain for
either its key or contract. Old fills/source history and original projection rows
are preserved; no fictitious close, P&L or equity adjustment is created.

61 targeted checks passed for source cleanup plus step/retry integration. An
additional check on copies of both current databases archived exactly
`v6|VG|rsi|2026-09-30T15:00:00`, preserving metadata and the broker journal.
The repair deployed at **10:59:04 Central**, with zero open orders and WFC ×26
held. Execution policy/model/risk checks and the consumed retry IDs are unchanged.
Latest manifest SHA:
`51e61f0bd400d6263bac362398e1bb03e9e5c271f0fa9fa6f11a4bd3baef3f8b`.
Backup: paper state's `runtime-revisions/scanner-contract-reuse-v3-20260930/`.
Receipts/script: `nn_meta/validation/v6-scanner-contract-reuse-20260930/`.
The 11:00 scheduled scan archived exactly that VG projection and passed exit
monitoring and the fresh provider-access check. It completed in **256.537 seconds**
with 308 candidate rows and zero detection errors: 444 symbol results and five
securities without a current bar. Normal broker polling remained independent.

## V6 update and V7 run

At 10:40 Central, V6's September 28 catch-up is **325/449 symbols** (72.4%).
All 124 remaining error entries report deadline/timeouts. The 05:32 restart
ended at the 08:00 market-hours cutoff; successful checkpoints are retained.
No training or new model freeze has started. `healys-v6-continual.timer` next
fires at **15:45 Central**; daily-input and calendar guards still apply. This
research update is separate from the deployed V6 paper model.

V7's no-overall-cutoff supervisor completed at **08:18 Central**, after two
continuation passes. All **93/93** selected securities completed pending replay:
**21,624,449 horizon-target evaluations**, 251,983 cohorts, no worker failures.
Per-wave receipts total **129,873 pending input requests** (not a deduplicated
capture-window census). The frozen replay queue is complete; full-universe
execution discovery and additional actual-input acquisition/reconciliation remain.
**7-3 stays open; V7 training has not started.** Do not rerun the completed
109,825-window capture or this completed frozen replay without new evidence.

MRHA migration at 10:39:37: **182.484/229.378 GB logical**, 175,649/504,516
files, status running, no error. Local free space about **198.7 GiB**. Remaining
storage migration is independent; active working databases/models stay local.
Steam untouched. Exact service, campaign and artifact pointers remain in
[CURRENT_STATE](../CURRENT_STATE.md).
