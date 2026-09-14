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
