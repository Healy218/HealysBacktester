# V7 dividend completion — September 18, 2026

The dividend portion of item 6-1 is complete under the recorded reconstruction
policies. The final sealed artifact is
`nn_meta/validation/v7-dividends-complete-20260918`.

| Final consumer audit | Result |
|---|---:|
| Original provider records reconciled | 10,428 |
| Resolved records / pending noncash records | 10,194 / 234 |
| Cash price adjustments | 4,854 |
| Individually dated cash payments | 4,918 |
| Uncompiled dividend groups / missing cash treatments | 0 / 0 |
| Actual raw price boundaries verified | 4,854 |
| Original history rows retained | 667,239 |
| History sessions admitted under the existing policy | 587,284 |
| Auxiliary dividend events with separate identity boundaries | 16 |
| Modeled FX payments / provider precision payment | 27 / 1 |
| Reported settlement coverage | 2022-01-01 through 2027-01-08 |

## What changed

Primary issuer, fund, SEC and depositary evidence resolves ordinary amounts,
special components, ADR units, record dates and payment dates. Each distribution
adjusts prices once; separately dated components accrue and release individually.
All original records survive in the exact resolved/pending partition. Reviewed
false records, cancellation, unrelated instruments, duplicate aliases and the
AMC share distribution create no fictitious cash.

The user explicitly approved the remaining currency rule: use the last official
FX observation strictly before the ex-date, then freeze that USD amount for both
price adjustment and cash. SU and CCJ use native CAD; PBR uses BRL **per ADR**
already supplied by its depositary. Bank of Canada daily rates, native amounts,
calculation and policy identities are retained. These 27 payments are modeled,
not assertions of actual depositary conversion or net investor proceeds.

The 19 final identity/boundary reviews include three missing March 14 raw closes,
the historical ANTM/ELV label, and successor/predecessor securities. The auxiliary
boundary view preserves the original trading membership byte-for-byte. Five
additional cash identities use their actual dated FIGIs or primary-confirmed
CUSIPs; they are not aliases for predecessor holdings. A funded predecessor
position earns no successor dividend unless a separate lifecycle treatment first
establishes the successor holding. First-day features remain cold on March 15.

The final SILJ conflict is resolved by the visually checked issuer ICI 2025 tax
table, page 2: record/ex December 29, payment December 30, cash $0.55410448.
That primary report supersedes conflicting dates in the website's backfilled
distribution feed. Foreign-tax reporting gross-up is not additional cash.

One finite exception remains explicit in provenance, rather than an unresolved
cash event: ETHE September 3 has original USD amounts $0.025932 and $0.0259 with
identical dates. Its primary September page was unavailable (403/429), and the
captured SEC index has no filing after August 7. The bounded decimal rule retains
the more precise original amount because it rounds exactly to the other report.
The issuer filing establishes cash units, **not** the September amount. The event
uses matching-provider reconstruction and `primary_amount_verified=false`.
No global tolerance, currency conversion or net/gross inference was introduced.

## Verification and use

`scripts/finalize_v7_dividends.py` verifies all bound input bytes, every original
record's partition, all payment components, captured clocks, every cash factor
against actual preceding raw prices, and the unchanged canonical coverage grid.
The actual portfolio consumer processes all 4,918 payments with zero holdings:
cash stays at $100,000 and no receivable appears. Funded accounting tests cover
separate releases, exactly-once accrual and predecessor/successor isolation.

The final artifact contains `actions.json`, `events.json`, `unresolved.json`,
`coverage.parquet`, `auxiliary_cash_actions.json`, `price_boundary_checks.json`,
the full input bindings and the consumer report. The strict final gate sets
`dividends_complete=true` only after the complete audit. Intermediate census
reports intentionally never establish that gate on their own.

Full regression result: **2,338 passed plus 18 subtests**, 19 existing warnings,
127.33 seconds. Log: `/tmp/v7-dividend-tests-final-20260918.log`.

Use the canonical `v7-security-history-20260917-gap-r2` for study coverage.
`v7-dividend-boundary-history-20260918` is a finite dividend compilation view,
not a replacement universe or full feature history. Preserve every sealed
producer/review; new revisions need new artifacts and appropriate version binds.

## Remaining scope

Item 6-1 stays open for the 234 noncash records, unresolved identity transitions,
option deliverables and complete held-position lifecycle coverage. All seven
overall readiness items remain gated. Effective-session availability is an
explicit historical reconstruction; actual publication vintage, broker posting,
withholding and fees are not claimed. No training, strategy replay, deployment,
V6 policy change or trading-edge improvement follows from dividend completion.
