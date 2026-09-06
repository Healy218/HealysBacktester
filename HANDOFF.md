# Handoff — External comparison deferred; all 13 groups retained

September 6, 2026, Chicago. Work is on main in the primary checkout.

The user explicitly confirmed moving past external TradingView comparison
while retaining all thirteen groups. Earlier full freeze launch authorization
persists. The full freeze has NOT started.

## Implemented change

NN_META_V6_PARITY_POLICY=deferred selects the distinct
2026-09-06-tv13-option-ticks-unverified-v1 feature contract. Default policy
remains verified. Deferred manifests omit parity_pack, declare
external_comparison with status deferred, research_only true and a nonempty
reason, and supply the complete feature_schema. Context must match those
settings. All 13 groups / 96 TV columns, 10 tick columns and 20 proposal
families remain present. No fake passing comparison report is made.

Verified loaders reject the unverified contract. Manifest/context hashes,
exact history origin and bytes, causal availability, and tick-store coverage
remain checked. The wrapper inherits the explicit policy and still requires
a sealed manifest. See docs/specs/V6_EXPANDED_INPUTS.md.

## Pending input and next phase

Actual per-symbol 2D boundaries and VWAP context are absent, separately from
external output comparison. Asked the user asynchronously whether to use
explicit local calendar/VWAP research assumptions or require TradingView
context. No answer has arrived. Do not interpret the comparison waiver as
having already answered that question. A local policy needs a fixed calendar
anchor, explicit VWAP reset semantics, minimum tick assumptions, per-symbol
bar hashes and clear provenance; never call it observed or TV-verified.

After materializing context, run the existing full request planner, review
the inventory, capture and materialize full tick stores, seal a fresh final
input manifest, and launch the full expanded freeze. The existing two-contract
SPY tick pilot covers one 15-minute window only. Do not start a reduced core
freeze and call it expanded v6, or mutate an active campaign's input manifest.

## Preserved state

Repaired candidate: audit-repair-20260905-final. Retired core pilot and
untracked nn_meta/artifacts_v6/ are untouched. No downloads, training,
deployment, notifications or trading actions occurred in this continuation.
The signed-in browser is no longer needed for the deferred comparison. Its
access state and export paywall are retained in
handoff-history/HANDOFF-2026-09-06-before-comparison-deferral.md.

## Validation

Full suite: 1,419 tests and 18 subtests passed, 11 warnings in 47.13 seconds.
Diff and launcher shell syntax checks pass.
