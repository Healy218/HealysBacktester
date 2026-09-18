# V7 action coverage and targeted missing-input repairs

The user accepted the documented provider-union no-event reconstruction
assumption. The active policy is
[`V7_NO_EVENT_ADMISSION_20260917.json`](../specs/V7_NO_EVENT_ADMISSION_20260917.json),
identity `ea9b8c5292fc1ad758556b78ce9e4cb35f70995a581918f0cf829fdd662e8360`.
This decision is settled. Consumers retain completeness and historical publication
as unverified; applicable unresolved records still block their histories.

## Full census and original-record reconciliation

The rebuilt grid retains 667,239 rows, 591 securities and 1,129 sessions:

| Treatment | Sessions |
|---|---:|
| Assumed no event | 574,811 |
| Compiled event with assumed coverage | 4,349 |
| Unresolved action records | 35,447 |
| Unresolved identity | 52,632 |
| Total admitted for historical features | 579,160 |

These are full history-grid counts, not entry-eligible exceptions. Absent
pre-IPO listings are not automatically missing data. The 162 eligible identity
mismatches and 172 distinct eligible identity/zero-observation exceptions remain.
No held-position treatment or full-security readiness is claimed.

The inventory has 10,428 original records: 8,964 consumed by 4,481 compiled
cash/split events, 90 retained as reviewed unrelated-instrument records and 1,374
still unresolved. The compiled total contains 4,462 reconstructed events
(4,373 cash and 89 splits) plus 19 publication-reviewed events; all 18 SPY
distributions remain. All prior 4,433 complete event objects are preserved.

Finite exact-date listing/share-class reviews resolve 45 cash groups involving
reused B, FB, FIG, GOLD and SPCX tickers. Their original 90 records remain in
`reviewed_unrelated_instrument` treatments. This does not add study exclusions,
infer successor relationships or create price factors.

## Named acquisitions and history repair

`V7_GAP_HISTORY_REPAIR_20260917.json` identifies the missing 2025–2026 GAP input.
The retained raw capture restores 425 observed sessions with exact scoped
identity `BBG000BKLH74`, using already retained original daily listing captures.
The history now has 614,564 observed rows, 43 listed zero-observation rows and
52,632 rows without a selected listed source. The other 666,814 history rows
remain unchanged. An independent comparison caught a preexisting two-candidate
routing count being reduced to one during supplementation. The repair now
preserves that count and source status; a regression test covers it. Only the
`-r2` history and downstream artifacts below are current. Preserve earlier
outputs as superseded evidence.

`V7_ACTION_PROCESS_TAIL_20260917.json` identifies 45 tickers whose otherwise
matching cash records lacked an Alpaca counterpart within the original process
window. The bounded September 16–December 29, 2026 process-date query returned
49 records, 48 within the existing effective-date scope. These are scheduled
process/payment dates queried at capture time, not future observations. Effective
study dates remain March 15, 2022–September 14, 2026. The combined repairs add
48 compiled cash events. Revised existing provider IDs are rejected.

Alpaca filters corporate-action queries by process date and does not guarantee
timely record creation. Pagination alone cannot prove no event was omitted.
The accepted policy is explicitly an assumption, not a stronger claim about
these captures. [Alpaca endpoint documentation](https://docs.alpaca.markets/us/reference/corporateactions-1).

## Consumer enforcement

`action_coverage.py` reconciles every original record before classifying dates.
Dated unresolved records block applicable dates through any known alias;
undated records conservatively block the involved security's history. Quiet
responses do not admit anything without the authorized policy. Held-position
admission remains false throughout.

The production proposal builder requires `--action-coverage` and verifies its
receipt, transitive dependencies, policy, exact required dates, source tickers
and event IDs. Compiled events load through `ordinary_actions.price_action` so
reconstruction/publication fields survive. Feature-store declarations and resume
identities retain the coverage declaration even when no event occurs.
Supplementary raw captures require a binding through the selected daily input;
ambiguous overlapping captures cannot silently replace prices.

## Current immutable artifacts

All names below are under `nn_meta/validation/`:

- `v7-security-history-20260917-gap-r2`
- `v7-action-inventory-20260917-tail`
- `v7-ordinary-actions-20260917-tail-gap-r2`
- `v7-other-instrument-actions-20260917-tail-gap-r2`
- `v7-action-coverage-20260917-tail-gap-r2`
- `v7-coverage-consumers-20260917` and `v7-coverage-feature-check-20260917-SPY`

Raw inputs are retained under `nn_meta/data_v7/gap-history-repair-20260917`
and `nn_meta/data_v7/action-process-tail-20260917`; GAP daily inputs are at
`nn_meta/validation/v7-gap-daily-20260917/{2025,2026}`. Earlier coverage captures
retain the pre-policy census; they are historical, not current admission inputs.

## Validation

All 4,481 event factors and daily returns pass independent 50-digit decimal
checks; maximum absolute return error is 1.24e-15. All 4,481 causal prefix checks
pass. The actual proposal input loader accepts a two-session SPY boundary with
780 observed minutes; its retained 15-minute, one-variant store has 52 feature
observations and preserves both policy declarations. This bounded check does not
claim a complete feature/proposal store.

Full suite: **2,070 tests and 18 subtests passed**, 19 warnings, 128.77 seconds.
The retained suite log and source bindings are in `v7-coverage-tests-20260917`.
Acquisition usage after the named repairs is 63,056,260,023 bytes against the
250,000,000,000-byte shared ceiling, with no outstanding reservations.

## Remaining item 6-1

The remaining 504 simple groups include 358 unreviewed units/terms, 23
single-provider groups, 57 combined-event groups, 44 mismatches and 22 matching
groups lacking identity/adjacent continuity after unrelated instruments are
separated. All 213 complex records remain explicit. Undated name changes account
for many blocked otherwise known sessions; dated identity and primary notices
must resolve their roles without inventing effective dates. GAP's restored
prices alone do not resolve its undated name-change record.

Actual held stock entitlements, payment/settlement clocks, option deliverables
and lifecycle continuity still require executable treatment. This milestone is
part of 6-1; full feature production, execution, assembly and readiness remain
queued in TODO. V6 operation and unrelated workspace changes are preserved.
