# ETFE contract declaration and source blockers

October 3, 2026. The user selected ETFE-0 and requested the history boundary
and feature/execution/evaluation/acquisition contracts. Four definitions are
now declared with source bindings. **ETFE-0.contract remains open:** the exact
provider-global start and required dated/provider references are not proved.
No integrated pilot, bulk acquisition, dataset build or training was launched.

## Delivered definitions

- [Source contract](../specs/ETFE_CONTRACT_20261003.md): exact fixed-end civil and
  stock-session UTC bounds, evidence limits, final-vintage availability assumption
  and explicit blockers H1/R1/R2/P1.
- [Feature contract](../specs/ETFE_FEATURES_20261003.md): exhaustive 221-field
  mapping, thirteen source scopes, 442 model inputs including missingness masks,
  causal lagged option windows, daily surface formulas and native warmup rules.
  Ten quote/tick fields are replaced by trade/bar fields; seven daily option
  context names change with the VWAP semantics. All strategy scope remains.
- [Execution contract](../specs/ETFE_EXECUTION_20261003.md): whole contracts,
  1% volume participation, fixed pre-cost leg stop denominator, costs, stale
  valuation guard, partial exits, settled-cash rolls, dated physical delivery and
  boundary-censored outcomes. These are declarations, not execution validation.
- [Evaluation contract](../specs/ETFE_EVALUATION_20261003.md): three expanding
  folds, ten-session gap and full-horizon purging, 84 required fits including
  21 final refits, fixed objectives/parameters/thresholds, baseline comparisons
  and accepted/rejected/blocked distinction.
- [Acquisition contract](../specs/ETFE_ACQUISITION_20261003.md): demand inventory,
  immutable page chains, duplicate/correction/missingness protocol, historical
  references and a bounded representative pilot with resource/stop rules.

The V7 weekly-grid audit found symbol-level eligibility in `weekly_expiry.py`,
not a family-specific extension table. The new contract records that distinction
and refuses to carry over the unfinished all-target V7 demand loop. Native TV
formulas/defaults are source-pinned, not rewritten as unverified approximations.
External Pine parity remains unverified under the inherited local RTH policy.

## New provider observations

`scripts/probe_etfe_contract_boundary.py` verifies the immutable v2 setup before
issuing a maximum of ten read-only Alpaca GETs. The sandbox-only r0 attempt
recorded ten transport failures; the authorized network r1 run completed ten
HTTP 200 requests with no transport failures, at October 4 01:08:37 UTC
(October 3 20:08:37 Central). Both attempts remain separate.

Six terminal empty responses cover pre–January 18 14:30 UTC bars/trades in
three already observed January 19 calls. Existing January 18 samples remain
the earliest observed examples, not the global first timestamp. Historical
routes require named contracts; finite sampling cannot establish provider-wide
absence. H1 needs authenticated provider boundary evidence or an exhaustive
provider-wide inventory. No unsupported quote endpoint was retried.

Three current expired-contract controls returned size 100, multiplier 0 and
T+1 deliverables for January 2024. Their present-day fields cannot override
dated OCC terms/settlement. The QQQ example carries a 409.78 strike; no ordinary
unadjusted contract identity is assumed from that symbol. R1 needs dated
series/adjustment/deliverable evidence and historical discovery completeness.

The stock calendar reconfirms October 2 13:30–20:00 UTC and October 5 settlement
date. The civil acquisition cutoff is October 3 04:00 UTC exclusive. Current
Nasdaq web/PDF class lists disagree on VOO inclusion in the 16:15 list; R2 needs
effective-date and expiration-day/early-close evidence. The source contract
links each primary source. P1 remains a historical trade-route feed confirmation;
condition filtering and occurrence identity policies are explicitly declared.

## Verification and preserved boundaries

The portable [receipt](2026-10-03-etfe-contract.json) binds all contract bytes,
the 42-file inherited formula snapshot, the v2 setup plan and the raw live
boundary controls. `scripts/verify_etfe_contract.py` checks hashes, every field's
required metadata, quote/timeframe replacement, thirteen scopes and the 84-fit
census. The inherited 221-field inventory also matches the current V7 row schema.
Contract/link/syntax verification and original/v2 setup integrity are recorded
in the receipt. No broad regression, capture campaign or performance run was
needed to validate these declarations. No EXPERIMENTS verdict or maturity
increase is created.

TODO marks the four definition tasks complete and keeps source/history admission
open. ROADMAP retains ETFE-0; the pilot stays gated. CURRENT_STATE selects the
declaration/evidence locations alongside the unchanged setup. Unrelated dirty
code/documents and V7 archives remain preserved. Resolving the remaining evidence
requires an immutable contract successor, not editing readiness flags.
