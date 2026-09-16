# September 16 user-directed midpoint paper pricing

## Decision and semantics

The user explicitly requested one option price for both simulated buys and
sells: a valid provided mid/midpoint when present, otherwise the bid/ask average.
The follow-up about `last` was clarified: retain last trade as reference if
provided; it is not substituted for midpoint. This supersedes the previous
ask-entry/bid-exit paper convention for V6 and V7. It does not claim midpoint
execution is guaranteed or rewrite historical completed trades.

Shared helper `options/paper_pricing.py`, policy `option-midpoint-paper-v1`:
positive finite uncrossed bid/ask; recognize `mid`, `midpoint`, `mid_price`,
`midpoint_price`; supplied values must lie inside the current spread and aliases
must agree. A null midpoint is absent; invalid supplied values fail closed.
Without a supplied midpoint calculate bid/2 + ask/2. Keep both sides, price
source and the explicit simulated flag. Latest trade fields are preserved by
the V6 quote adapter when present, but are not fill/mark references.

V6 applies the same base price to entries, closes and both roll legs. Alerts
identify simulated midpoint and per-side costs. V7 QuoteTape uses it for buys,
sells and marks; cash-ledger, replay, shared portfolio and physical-ledger
**option** equity all consume the midpoint price. Observed stock liquidation
and stock valuations after funded exercise retain the stock execution policy.
Existing 0.10% fee +0.05% slippage per side remain separate costs: unchanged
midpoints yield approximately -0.29955% after a complete round trip.

This amendment does not alter model predictions, entry ranking, strategies,
underlying stops, quote freshness, size/condition rules, latency or deadlines.
The previously identified generic strategy/5%-stock-stop label is still generic;
it was not reclassified by this pricing-only change.

## V6 deployment and transition

Candidate branch `ops/v6-midpoint-20260916`, commit
`4fe7e5fff512e3147f6dc5d17b04f61ea791f1ed`, derived from deployed `5787909`.
Source checkout `/tmp/healys-v6-midpoint-20260916`; main contains the shared
helper and activation utility. The existing untracked V6 files in main were
edited in place but remain unstaged there; their exact production versions are
committed/pushed on the isolated runtime branch. No unrelated V6 work was swept
into main. Production source arrived via `git pull --ff-only`, never scp.

On a copied real ledger containing open UBER and CELH, the transition rebased
the current open paper leg from its retained entry ask to retained midpoint,
recorded old/new basis in an immutable pricing-change event, and left completed
legs, closed records, allocation amounts, realized equity, signal state, cycles
and outbox unchanged. Repeating it made no further changes. A separate unchanged-
quote diagnostic produced only the -0.29955% round-trip costs for both positions.
These were copied-state diagnostics, not live fills or messages.

Narrow activation utility `scripts/activate_v6_midpoint.py` permits only the two
reviewed runtime-module changes (`v6_market.py`, `v6_portfolio.py`) and the new
shared helper. Every other prior runtime dependency must match the previous
activation. It requires passing runtime/midpoint tests, unchanged prior feature
proof and hash-bound copied-ledger evidence. Prior feature/model/signal/timing
proof remains relevant; previous ask/bid execution prices are explicitly
superseded. No blanket relabeling of old execution evidence is allowed.

Actual home deployment completed successfully. It stopped the forward timer,
waited for any active pass, held the producer lock, made SQLite and activation
backups, pulled the candidate, verified all runtime hashes, applied the audited
transition and installed the activation before resuming the timer. All positions
had closed before deployment: **zero live entries required rebasing**. The ledger
retained 13 closed positions, 35 cycles, 26 exported outbox records and realized
paper equity 0.6867286044611687. No reset or retrospective recovery of old losses.
The new activation SHA256 is
`dccdd2d167e18d28a23d53cd005e2d3161e9adc8f90cc863f41117f114fcfd56`.

Evidence: `nn_meta/validation/v6-midpoint-20260916`, including full copied-state
report, before/after databases, actual deployment report, original/replacement
activation, transition, Git pull output, exact audit/deployment sources and tests.
The post-deployment 20:00 UTC producer completed in 235.25 seconds: status
`recorded`, phase `complete`, no error. Five selected entries were unfilled, so
this pass did not produce an actual midpoint entry. It recorded cycle36 and
preserved the equity/closed-trade/outbox counts. Terminal application status is
retained as `deployment/post-deployment-status.json`.
Read-only verification of the server incoming payload confirmed the midpoint
policy, runtime commit `4fe7e5f`, recorded cycle36 and unchanged equity/history.
No manual test alert or broker order was sent.

## Tests and V7 scope

Isolated candidate: **1,574 tests +18 subtests**, 16 warnings, 64.21 seconds.
Its first run had two CLI-preview failures because the isolated checkout lacked
its venv link; after linking the existing environment the complete rerun passed.
Main: **1,834 tests +18 subtests**, 18 warnings, 91.33 seconds.
An earlier main run exposed four old bid-only synthetic mark fixtures; those
were updated to supply explicit midpoint marks, then the complete suite passed.
No runtime pricing code changed after these passing suites. Tests include wide
unchanged quotes, provider-mid precedence, invalid/conflicting mids, last-price
non-substitution, entry/exit/mark equality, cash reconciliation, roll recovery,
realistic open-ledger migration and guarded activation amendments.

V7 amendment: `docs/specs/V7_PAPER_PRICING_20260916.json`, bound by
`V7_ACTIVE_INPUTS_20220315.json`. The full-readiness scope now includes its hash,
and active-input verification requires the declared quote policy to equal the
implemented policy. Historical evaluation splits and physical-stock policy
remain as previously declared. Earlier ask/bid option fills, marks, labels and
portfolio results must be rebuilt under this policy; never relabel them.
Changing the active manifest also invalidates strict parent bindings in the
existing raw-daily/surface summary chain. Raw observations remain unchanged;
reverify/rebuild the derived bindings before downstream daily integration.

Latest readiness `nn_meta/validation/v7-readiness-20260916-midpoint-checkpoint.json`:
active inputs, membership and coverage pass; all eight substantive stages still
need full-universe evidence. **V7 is not ready to train.** The causal daily draft
remains parked at `/tmp/v7-causal-daily-wip-20260916.py`, untested and unadmitted.
