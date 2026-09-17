# Arithmetic midpoint, option stops and ITM expiry

The user explicitly selected arithmetic `(bid+ask)/2` for simulated buys, sells
and marks; option-premium declines from entry of 7.5% for V6 and 12.5% for V7;
and ITM liquidation 15 minutes before the option class's regular close on expiry
day. Strategy sell signals remain. The generic 5% underlying stop is removed
from held-position exits. Existing 0.15% per-side bookkeeping costs remain
separate from the premium-return threshold. Supplied mid/last fields cannot
override the arithmetic average. Completed history is preserved.

A fresh quote that triggers a stop also supplies the simulated sale price. No
second quote request or broker fill proof is required. Quote gaps remain visible;
the next valid observation can execute beyond the threshold. V7 records the
observation/execution clock separately from the original quote timestamp, so a
fresh five-second-old quote does not backdate the portfolio exit. Unknown or
stale expiry stock marks cannot be treated as OTM. Existing OTM roll and physical
fallback semantics remain; the change does not complete their historical gates.

## V6 deployment

Runtime commit `d252c5190c3ca261136966ffe43432b160adfc84`, isolated branch
`ops/v6-option-risk-20260916`, was deployed by Git pull into
`/home/healy/Coding/HealysV6`. The activation amendment permits only six reviewed
module changes and four additions. All other frozen runtime sources and prior
model/feature evidence remain bound. Source comparison verifies that entry
calculations are unchanged after excluding only the held-exit block/helper and
a descriptive context field. Entry/exit signal conflicts retain the simulator's
entry precedence and opposite-entry reversal rules, tested against vectorbt.

The one-minute risk worker uses the current option quote independently of the
slower stock-feature scan. Alpaca SIP stock midpoint is required only for ITM
classification at expiry. An atomic leg comparison rejects a stale risk decision
if the strategy worker has rolled the position meanwhile. SQLite transactions
prevent double sales; alert-spool exports share a lock. No broker orders occur.

Deployment stopped the forward timer, held its lock, checked the book was empty,
backed up SQLite/activation, pulled the reviewed commit, verified source hashes,
installed the new activation and verified risk units, then resumed the forward
timer. **All 13 completed records, realized equity 0.6867286044611687 and the
entire logical ledger stayed unchanged. Zero open legs required migration.**
The risk service completed successfully with exit status 0; its timer is active.
The activation SHA is
`d7ce5e3ebbcc58ddb894564b113cc35c210d0d35f4558123944f8cacf8c02f34`.
This verifies deployment with an empty book, not a live stopped-position outcome.

The September17 follow-up d252c51 also guards OTM expiry decisions against a
concurrent contract replacement; the prior d415733 deployment is retained as
history. It changed only the two execution callers and one regression. Both
worker locks were held and the ledger again remained unchanged.

Evidence: `nn_meta/validation/v6-option-risk-20260916` (latest under `roll-guard/`), including exact audit and
deployment scripts, before/after ledger snapshots, source comparison, activation,
unit files, command logs and copied-state/production status. Candidate tests:
**1,610 passed plus 18 subtests**, 16 warnings,65.15s. Regression coverage includes
unchanged wide spreads, both option rights, single-quote stop sales, quote-gap
recovery, expiry timing, Alpaca stock source/freshness, stale-leg races and all
16 signal combinations for each held direction.

## V7 execution binding and remaining work

Current execution-aware active manifest:
`docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`; policy:
`docs/specs/V7_OPTION_RISK_20260916.json`. The old
`V7_ACTIVE_INPUTS_20220315.json` remains byte-identical because raw-history and
action artifacts bind it and their producer scripts. Raw-only producers keep
that predecessor default. Readiness verifies that only the two execution-policy
fields changed, allowing later readiness metadata updates but no alteration to
dates, universe, input hashes, plan, sectors or exclusions. Historical pricing
specs remain preserved. No existing label/path is relabeled under the new policy.

The V7 proposal simulator disables generic stock stops. Option replay applies
the 12.5% premium stop and ITM expiry rule, and shared portfolio chronology uses
the explicit execution clock. Readiness requires full-universe evidence for these
rules in assembly, in addition to all existing gates. The current check passes
its three input/membership/coverage checks and rejects **all eight unfinished
stages**. Full labels, compact storage, daily/sector/tick integration, actual
quote demand, physical adapters, training assembly/runner and resource evidence
remain incomplete. No full training launched.

Main final suite: **1,957 tests plus 18 subtests**, 18 warnings,102.97s.
Evidence main-bound-tests.log/xml is retained alongside the candidate evidence.
The real AAPL input consumer also verified 15,600 raw minutes,40 routed sessions
and33,877 parent bindings against the unchanged captured history/actions. No
market data was downloaded for this amendment.
