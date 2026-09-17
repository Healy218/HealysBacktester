# V7 6-1 — exact-date share-class identity resolution

Retained original daily listing captures support **27 exact-date resolutions
across 14 symbols**. The rebuilt full history reduces eligible identity/source
mismatches from **186 to 162**, and the unchanged ordinary-action compiler admits
four additional splits: **BOIL, LABU, TMF and YINN**. There are now **4,433 compiled
events**, including all 18 SPY distributions. **6-1 remains open; V7 is not ready.**

## Evidence and interpretation

The original compressed daily records retain `share_class_figi`, although the
normalized identity panel omitted it. [OpenFIGI's official definition](https://www.openfigi.com/api/documentation)
identifies the share-class FIGI as linking composite identifiers for the same
instrument across countries. We infer instrument continuity only for finite
reviewed dates where this identifier and all relevant listing fields match an
earlier known scoped listing. This is identity evidence, not historical publication
evidence or a conclusion about merger consideration.

For every review, the captured ticker, share-class FIGI, primary exchange,
instrument type, market, locale, currency and issuer CIK must match the earlier
anchor. CIK may be absent only in both original records; the share-class ID must
be present. Both listings must be active and on allowed US exchanges. A composite
ID assigned to another scoped security is rejected. Each review binds both original
record hashes, exact dates and the target scoped security. All five exchange
captures for each used date are verified for query, page integrity and uniqueness.

The original provider composite FIGI is preserved in `provider_composite_figi`;
`resolved_share_class_figi`, resolution type and review hash are separate output
fields. The original capture and panel remain unchanged. A temporary canonical
panel supplies reviewed rows to the existing full-history selector. No review
creates an absent listing, fills a price, propagates to another day or uses a
future anchor. Different or missing share classes remain unresolved.

| Symbol | Exact reviewed dates |
| --- | --- |
| BLK | 2024-10-01 |
| BOIL | 2024-11-07 |
| COUP | 2023-02-28 |
| DISCA | 2022-04-04, 2022-04-05 |
| DKNG | 2022-04-04, 2022-04-05, 2022-04-13 |
| LABU | 2023-12-04 |
| MCD | 2023-03-16 |
| SIRI | 2024-09-09 |
| TMF | 2023-12-04 |
| TWTR | 2022-10-28 |
| VMW | 2023-11-21, 2023-11-22 |
| X | 2025-06-05, 2025-06-06, 2025-06-09, 2025-06-10, 2025-06-11, 2025-06-12, 2025-06-13, 2025-06-16, 2025-06-17, 2025-06-18 |
| XOM | 2026-07-01 |
| YINN | 2022-05-31 |

The finite review specification is
`docs/specs/V7_SHARE_CLASS_IDENTITIES_20260917.json`. Rebuild from the original
selected history plus cumulative reviews, not from an already resolved history;
the command rejects a baseline that would erase earlier resolution evidence.

## Full-history and action effects

The full grid remains **667,239 rows /591 securities /1,129 sessions**. There are
598 continuity spans, 614,139 observed rows, 53,057 rows without a selected listed
source and 43 known-listed rows without stock observations. Of the 27 reviewed
dates, 23 restore actual observations and four remain known zero-observation
dates. Exactly 24 dates lie in entry-eligible membership; three affect history
outside membership. All other **667,212 raw rows** are unchanged, as are each
affected security's raw-history prefixes before its earliest reviewed date.

The 162 remaining eligible mismatches span 13 symbols: ATVI 12, BLK 22, CCL 16,
DISCA 14, DKNG 18, RKLB 4, SGEN 10, SIRI 15, SWTX 17, TWTR 1, VMW 5, X 7 and
XOM 21. There are still 59 zero-bar eligible sessions, overlapping 49 unresolved
identity sessions: **172 distinct eligible exception sessions**. Identity resolution
does not provide executable lifecycle/held-position treatment for these dates.

The updated action set has **4,414 reconstructed events (4,325 cash /89 splits)**
and 19 retained publication-reviewed events, for 315 security IDs. It consumes
**8,868 of 10,380 original provider records**, leaving **1,512 explicit unresolved
records**. The 4,506 matching groups partition into 4,414 reconstructed, 18 retained
Apple reviews, 66 missing effective-day identities and eight missing adjacent
continuity cases. The remaining 597 simple groups are those 74 cases plus 354
unreviewed terms, 68 single-provider, 57 combined-review and 44 mismatched groups.
The 213 complex records remain separate from group counts.

Every previous 4,429 event keeps its price/volume factors, availability/effective
clocks, replacement and admission basis. Restored continuity changes 47 event IDs
through their span bindings; this is a provenance change, not a factor change.
The four new splits retain the user's effective-session reconstruction assumption,
null publication availability and `publication_verified=false`.

## Consumer and regression verification

Independent verification compares the full raw grid and old/new event factors.
For each new split, independent 50-digit decimal calculations agree with actual
causal daily returns; maximum absolute error is 6.938893903907228e-16. Real captured
minute data exercises the causal feature path, adjusted price/volume factors and
unchanged pre-event technical/TV features:

| Split boundary | Observed minutes across two sessions | Price factor |
| --- | ---: | ---: |
| BOIL 2024-11-07 | 775 | 5 |
| LABU 2023-12-04 | 777 | 20 |
| TMF 2023-12-04 | 780 | 10 |
| YINN 2022-05-31 | 754 | 20 |

The BOIL case also builds an actual bounded MA feature store at
`v7-share-class-feature-check-20260917-BOIL`; every subreceipt and its declared
source bindings are verified and retained in the consumer report's inputs.
These checks complement the prior all-4,429 event checks and SPY/NVDA feature
stores. They do not constitute full feature production or held-position execution.

Focused tests: **33 passed** (24 new identity cases plus nine existing history
cases). Full repository suite: **2,034 tests +18 subtests passed**, 18 warnings,
125.01 seconds. The new tests cover source preservation, real selector integration,
prefix invariance, conflicting listing fields, missing IDs, scoped-ID collision,
future anchors, corrupt hashes, absent/ambiguous listings and duplicate reviews.
No production code changed after the suite. All commands finished successfully.

## Artifacts and reproduction

All artifact names below are under `nn_meta/validation/`:

| Artifact | Receipt SHA256 |
| --- | --- |
| `v7-security-history-20260917-share-class` | `1d1ff2dc83d4f19d9f632efdea1cb4d407be52aebfe127040473b94ce7d1b978` |
| `v7-ordinary-actions-20260917-share-class` | `ed1ab9fbffe572df8f75d706d14d2734616770d695c83396bb9025e0f3ed9403` |
| `v7-share-class-consumers-20260917` | `7c5d088c5ea4be4cad7fe0983e7d5031e4179e6a71ac61ee0186f738824f32e2` |
| `v7-share-class-tests-20260917` | `322d03a47751ffffeea663161c05a31ad2cabd51e4f745c93f176e65a45b2020` |

The consumer artifact retains `verification.source.txt`, source bindings and
`remaining_eligible_identity_exceptions.parquet`. The tests artifact retains the
full log and changed-source hashes. Original logs are
`/tmp/v7-share-class-history-20260917.log`,
`/tmp/v7-share-class-actions-20260917.log`,
`/tmp/v7-share-class-consumers-20260917.log` and
`/tmp/v7-share-class-suite-20260917.log`.

```bash
./venv/bin/python scripts/resolve_v7_share_class_history.py \
  --history nn_meta/validation/v7-security-history-20260917-routes \
  --identities nn_meta/validation/v7-daily-identity-panel-20260916 \
  --listed-captures nn_meta/data_v7/daily-identities-20260916 \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --reviews docs/specs/V7_SHARE_CLASS_IDENTITIES_20260917.json \
  --output nn_meta/validation/v7-security-history-20260917-share-class

./venv/bin/python scripts/compile_v7_ordinary_actions.py \
  --inventory nn_meta/validation/v7-action-inventory-20260916r2 \
  --reviews nn_meta/validation/v7-normalized-cash-reviews-20260916 \
  --history nn_meta/validation/v7-security-history-20260917-share-class \
  --calendar nn_meta/data_v7/exchange-calendar-20260916/calendar.json \
  --policy docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json \
  --output nn_meta/validation/v7-ordinary-actions-20260917-share-class
```

Use new immutable output names on rerun. No data acquisition, V6 change,
deployment, full research campaign or training launch occurred.

## Exact next work

Continue 6-1 with the 162 remaining identity dates, the 74 matching-action
identity/adjacency cases and the separately enumerated action conflicts/complex
records. Retained raw GAP daily shards cover 2024 only; seven matching GAP cash
groups in 2025–2026 lack the required GAP history, while old GPS shards have zero
observations in those years. That is a named missing input to assess before any
targeted capture; routing old GPS by ticker is not a solution. CCL/SWTX have no
captured matching share-class witness, and other remaining changed share classes
require lifecycle review. Preserve all original record partitions. Complete
no-event coverage and actual stock/option entitlements, payment/settlement and
held-position continuity remain required before closing 6-1.
