# Separate V6 Short-DTE experiment

Approved direction on September 13: preserve `v6-cash-repair-20260913` and
collect forward evidence alongside the existing experts. Do not rerun the
same configuration. This document defines the separate next experiment;
it has not been trained or enabled.

The short-DTE experiment must enforce **actual expiry minus decision date
from 1 through 9 calendar days**, after resolving a listed contract. The
existing nearest-expiry search can return more than nine days for a short
target and must not serve as this guard. Exclude 0DTE initially; evaluate it
as a separate policy with explicit same-day exit handling if requested.

Use the same frozen baseline proposals, 164-feature definitions, Massive
quote/trade feature policy, train-only missing-value handling, raw-price
contract selection and option cash ledger. Keep a distinct model, dataset,
scope, reports and expert identity. The existing V6 weights and outcomes
remain unchanged.

Predeclare the hypothesis: restricting the *actual* eligible expirations
allows the model to learn and allocate within the short-DTE universe. Do
not require or optimize toward a 1,000% winner. Keep original unbounded
realized returns in the audit; record the train-only magnitude target
winsor bounds separately. Any alternative regression loss or tail treatment
is a named additional trial, not an invisible change to the baseline.

Report the entire selection funnel by target and actual DTE: contracts
available, rows built, finite predictions, EV passes, best variant, allocation
acceptances/rejections and actual fills. Maintain five slots, one position
per symbol, the 10% position cap and original eligibility/risk comparison.
Count every experimental configuration in selection diagnostics.

Before a full training launch, test actual expiries of 0, 1, 9 and 10 days,
weekend/holiday boundaries, missing short expiries, aliases, ties and rolls.
Reject a roll into a contract outside the declared eligibility rule; document
whether cash is retained or the position terminates. Reconcile ask/bid fills,
contract multipliers, fees, cash availability and missed fills independently.

Freeze the design before evaluating a newly held-out period. Existing
May–August 2026 results have already influenced model selection and are
revalidation evidence. Compare the short-only experiment with unchanged V6
on the same new evaluation dates, including every rejected/unfilled proposal.


## September 14 handoff: next implementation and launch

The user requested that deployment finish and all notes be updated before
clearing chat and returning to train <10-DTE V6. The existing paper runtime
is now deployed at `d6660af`, release `v6-cash-repair-20260913`. This short-DTE
spec is the next task; its strict eligibility implementation, new dataset
and training campaign have **not** been completed or launched.

1. Inspect the actual selection/roll callers in `nn_meta/decision_contracts.py`,
   `nn_meta/weekly_expiry.py`, `nn_meta/build_meta_dataset.py`,
   `nn_meta/mark_stream.py` and `options/`. Add an explicitly named experiment
   contract; defaults must preserve the running broad-DTE V6.
2. Enforce 1 <= actual calendar DTE <= 9 after contract resolution for entries
   and every replacement leg. Freeze the target grid, tie policy, no-eligible-
   contract behavior and roll termination/cash behavior before building. Merely
   filtering existing rows by target DTE does not prove eligible actual fills.
3. Predeclare whether the new historical labels reproduce aggregate expiry
   marks or the now-authorized forward 15-minute expiry trigger. Record the
   execution convention and preserve a matching control; do not silently change
   this second dimension while describing the trial as DTE-only.
4. Use a fresh named scope and isolated source checkout, with separate rows,
   marks, model, diagnostics and future expert identity. Original repaired
   campaign is `nn_meta/campaigns/v6-cash-repair-20260913/v6/`; original expanded
   manifest is `nn_meta/expanded_inputs/v6-local-20260906/full-run/final-inputs.json`.
   Reuse only compatible hash-verified raw inputs/proposals; changed resolved
   contracts require matching quote/trade features, labels and marks.
5. Run boundary/causality/accounting tests and a bounded actual-data build before
   full work. Audit actual DTE on every entry/roll leg, the complete rejection
   funnel and both ledgers. Preserve genuine missing quotes and rejected fills.
6. Recalculate safe training CPU/memory limits with the live home scanner/data
   refresh present. The home host has 32GB; prior training allowed 24GB while
   the scanner allows 18GB. Those maxima cannot be allocated concurrently.
   Prefer measured scheduling/isolation; do not stop the paper experiment or
   change shared dependencies implicitly to make room.
7. Bind the new watcher, logs, resume/reboot handling and dashboard training
   identity to the exact new campaign/service. The current training watcher
   follows a completed campaign with Telegram OFF; the operating paper watcher
   stays separate. Verify the new service and watcher after launch.

No ready-to-launch command is claimed here: implementing strict eligibility
and its artifact/provenance contract precedes a concrete new launch command.
Keep the deployed model as the unchanged forward control. See the
[exact DTE/return audit](../reviews/2026-09-13-v6-dte-selection-audit.md) for why
short target variants lost the original EV/slot competition; do not invent a
200% cap or require any particular extreme-return winner.
