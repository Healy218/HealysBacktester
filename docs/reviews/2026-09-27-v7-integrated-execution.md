# V7-4 integration started — September 27, 2026

The current retained option paths now run through one shared PhysicalLedger.
This connects the existing option fills, cash/slot allocation, captured stock
quotes, reported settlement dates, final 4,918 cash entitlements, split/rename
inputs and noncash boundary guard. It does not regenerate proposals or refit a
model. Full V7-4 remains open: the retained five-path scope is not the universe,
and these real paths have not yet reached physical exercise or stock liquidation.

## Implementation

- `nn_meta/v7/integrated_portfolio.py` is a versioned continuation of the existing
  shared allocator. It reuses PhysicalLedger and preserves original source bytes.
  An accepted path's first missing input stops the shared ledger before later
  decisions/expiry; missing outcomes never filter initial allocation. Rejected
  candidates' data gaps do not block the accepted portfolio. Reservations and
  held positions survive incomplete capture. Unfunded exercise stays unresolved.
- `nn_meta/v7/integrated_inputs.py` connects retained source paths, indexed option
  quotes, captured Alpaca stock quotes, exact official expiry references and the
  existing ledger's settlement contract. Missing physical references stay explicit;
  no closing aggregate or synthetic intrinsic-value sale replaces them.
- `scripts/run_v7_integrated_execution.py` binds current receipts and seals the
  reconciled ledger, current exact gaps and source declaration. Constant-zero
  scores with stable proposal-id ties establish a plumbing baseline only.
- `scripts/run_v7_integrated_execution.sh` supplies the current completed input
  bindings. It accepts PATH_RECEIPT, QUOTE_INDEX and NEW_OUTPUT, all explicitly.

The old portfolio, physical, replay, capture controller and assembly producers
were not edited. Existing frozen bytes remain usable. New producers are now
bound by these runs; preserve them or version subsequent behavior changes.

## Actual run and advancement

1. Snapshot index `v7-integrated-quote-index-20260927-r1` reuses 3,522 finished
   entry packs plus 72 retained packs: 3,594 packs, 114,062 captures. The live
   entry job continues independently; later packs are not silently added to
   this immutable snapshot.
2. `v7-integrated-execution-20260927-r1` consumes all five existing r12 source
   cases. DIS and ABBV close through the same cash account. NVDA opens using
   10% of the then-current equity; the ledger pauses at its first missing mark.
   Later VKTX/FUTU decisions are not processed through that unresolved state.
3. The existing exact-gap acquisition command captures the required NVDA
   30-second-plus-one-nanosecond window into
   `nn_meta/data_v7/integrated-frontier-20260927-r1` (19,068 bytes).
   It publishes `v7-integrated-quote-index-20260927-r2`; original intervals survive.
4. Existing source replay advances to `v7-execution-discovery-20260927-r13`.
   Integrated replay advances to `v7-integrated-execution-20260927-r2`.
   All 1,466 ledger events (including zero-ownership cash events), three allocation
   decisions and 164 earlier valuation marks are identical; one new mark is added.
   Cash remains $87,596.26474814238 with one open NVDA option and no settlement
   commitment. Two source proposals are complete; three are not.

The latest shared gap is `NVDA240322C00910000`, quotes
`[1711038150000000000, 1711038180000000001)`. Its exact request is in the latest
integrated `capture-requests.json`. The complete source frontier also preserves
VKTX/FUTU's pending requests. Resume these artifacts; do not redo preparation,
packing trials, the hours/blackout decisions or the r0–r12 restart demonstration.

All shortened artifact names above are under `nn_meta/validation/`.

## Validation and remaining scope

58 focused tests pass across integrated execution, existing portfolio/physical,
frontier and reported-settlement behavior. New tests cover retained shared
allocation behavior, unknown versus sparse observations, rejected-path gaps,
missing-entry reservations, exact stopping, official-reference gaps, funded
exercise/stock sale/settlement and insufficient funding. The launcher passes
Bash syntax validation. The real resume comparison above also passes.
See `2026-09-27-v7-integrated-execution-verification.json`.

Full-scope path generation/capture, reference acquisition, actual held blackout
crossings, real exercise/stock-liquidation outcomes and their label horizons
remain unclosed. The runner accepts retained path reports; it is not an automatic
full-universe path-generation or download service. No real physical events occurred
in this five-path run; synthetic tests do not certify their full real-data coverage.
No training was launched. Entry acquisition remains running separately.
