# V7 6-1 — authorized ordinary-action reconstruction and consumer verification

The user accepted matching provider terms as historical reconstruction inputs,
applied only from the effective session, with that assumption retained explicitly
and conflicts/complex actions reviewed separately. The policy is recorded in
DECISIONS and `docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json`.

The full retained inventory now produces **4,429 chart-adjustment events** for
315 security identities: **4,410 newly reconstructed events** (4,325 cash and
85 splits), plus the **19 unchanged publication-reviewed cash events**. All
18 SPY distributions compile. Exactly **8,860/10,380 provider records** are
consumed; 1,520 remain explicit. **Item 6-1 remains open and V7 is not ready.**

## Admission and implementation

`ordinary_actions.compile_ordinary_actions` reconstructs normalized candidates
from original records and verifies their full equality before reconciling them.
A unique ordinary record from each provider must have exact matching terms and
effective dates, known supported units and no simultaneous conflicting category
or dated complex action. It never sums or deduplicates repeated source records.
Whole-group publication reviews take precedence once, retaining every previously
compiled field of the Apple events and corrected Devon $0.44 distribution unchanged.

The compiler uses the full selected security histories, including nonmembership
sessions. Cash adjustments require the exact preceding session's observed raw
close. Both adjacent days must have the same security and continuity span; a
reviewed same-security rename may change the stock ticker. Unknown identities,
identity breaks, absent prior observations and invalid factors remain explicit
failures, never unit factors or filled prices. Selected clocks must agree with
the captured calendar.

`ReconstructionAction` is compatible with `PriceAction` and is consumed by
`CausalPriceHistory`, `causal_daily.returns`, `CausalFeatures` and the existing
proposal basis. Its `available_at` equals the effective regular-session open
under the user's reconstruction assumption. It retains the policy identity,
`admission_basis=matching_provider_historical_reconstruction`,
`publication_available_at=null` and `publication_verified=false`. It rejects a
pre-effective availability or publication claim. This clock is **not** a claim
that the retrospectively captured record was historically published then.
The existing reviewed-publication path retains its original clocks.

The serialized feature-store declaration preserves the additional assumption
fields. Original provider IDs/hashes and the original source artifacts remain
bound in the output; no process date becomes a publication date. No historical
artifact was relabeled, overwritten or silently admitted.

`scripts/compile_v7_ordinary_actions.py` verifies inventory/review/history
receipts and source bindings before and after compilation, uses one inner
thread, enforces the 100 GiB disk reserve and writes a new immutable artifact.
It requires the explicitly authorized policy, with no boolean bypass for
unknown units, duplicate/complex actions or complete-history admission.

## Full census and remaining effects

| Treatment of the original 4,506 matching groups | Groups |
| --- | ---: |
| Newly compiled with explicit reconstruction assumption | 4,410 |
| Already covered by retained Apple publication reviews | 18 |
| Missing selected effective-day identity | 70 |
| Missing adjacent security continuity | 8 |

The additional reviewed Devon correction resolves a nonmatching group, giving
4,429 total compiled events. The remaining 601 simple groups comprise 354 with
unreviewed units/terms, 68 single-provider groups, 57 groups needing combined
review, 44 term mismatches and the 78 identity/adjacency cases above. The 213
complex **records** remain separate from these group counts.

The 78 matching exceptions are fully enumerated in `groups.json`. They include
ticker/identity questions for B, BMNR, BOIL, FB, FIG, FIGR, GAP, GOLD, LABU, SBET,
SIRI, SPCX, TMF, UVIX, XOM and YINN; adjacent-history questions for APLD, BYND,
LAZR, SOXS and SST; and KSS/LRCX/TMO cash events on the March 15 study boundary,
whose prior day is outside the selected history panel. These are exact remaining
consumer inputs. Some symbol events may belong to another security; the compiler
does not dismiss them or join them to the study security by ticker alone.

Every original record belongs to exactly one consumed whole event or the retained
unresolved output. `unresolved.json` preserves original records with a separate
compilation reason. It is not a list of 1,520 distinct events.

The policy does not prove complete no-event intervals: Alpaca queries are
process-date bounded and missing records remain missing. It does not establish
stock cash entitlements/payment availability, split settlement adjustments or
option deliverables. These chart inputs must not be interpreted as a cash ledger
or complete held-position lifecycle treatment. Reconstructed events explicitly
retain that held-position limitation. Existing 186 eligible identity mismatches
and 59 zero-bar sessions (192 distinct sessions) still need their previously
documented treatments. No additional issuer exclusions were introduced.

## Consumer and regression evidence

Every one of the **4,429 compiled events** was exercised with actual adjacent
raw daily observations through `causal_daily.returns` and `CausalPriceHistory`.
Independent calculations use 50-digit decimal arithmetic from original provider
terms or the retained reviewed cash total. Maximum absolute return error was
**1.2351231148954867e-15**. All 4,429 pre-event prefix comparisons are unchanged.
All 19 previous reviewed events remain unchanged, and the original-record
partition reconciles exactly.

Two captured minute-data boundary checks exercise real `CausalFeatures` and
feature-store construction: SPY March 18, 2022 cash distribution and NVDA June
10, 2024 split. Each uses 780 observed regular-session minutes across two days,
15-minute bars and two action epochs. Both preserve the pre-event technical/TV
feature outputs, apply the correct price/volume factors after the event, and
persist the reconstruction assumption in the feature-store declaration. These
are boundary integration checks with one configured MA variant each, not full
daily/context production or the full feature/proposal campaign of item 6-2.

Focused regression suite: **37 passed**. Full repository suite: **2,010 tests
+18 subtests passed**, 18 warnings, 125.10 seconds. New tests cover forward
splits/cash, consumer compatibility, prefix invariance, preserved assumptions,
review precedence, source/policy corruption, duplicate/complex/conflicting
groups, missing identities/prices, same-security renames and feature epochs.
No production code changed after the full suite.

## Artifacts and reproduction

All artifact paths below are under `nn_meta/validation/`:

| Artifact | Receipt SHA256 |
| --- | --- |
| `v7-ordinary-actions-20260917` | `84a75a1526331699695402ec8cc23a7c8f40a5630975bcb937234484cfb0944f` |
| `v7-ordinary-action-consumers-20260917` | `9d7fc9b8c61d7db8b8cbbec9972ffd2f1d0f8eda3151e22c73ec995cf6df9699` |

Boundary feature stores are `v7-ordinary-action-feature-check-20260917-SPY` and
`v7-ordinary-action-feature-check-20260917-NVDA`. Test evidence is retained in
`v7-ordinary-actions-tests-20260917`. Original logs are
`/tmp/v7-ordinary-actions-20260917.log`,
`/tmp/v7-ordinary-action-consumers-20260917.log` and
`/tmp/v7-ordinary-actions-suite-20260917.log`.

```bash
./venv/bin/python scripts/compile_v7_ordinary_actions.py \
  --inventory nn_meta/validation/v7-action-inventory-20260916r2 \
  --reviews nn_meta/validation/v7-normalized-cash-reviews-20260916 \
  --history nn_meta/validation/v7-security-history-20260917-routes \
  --calendar nn_meta/data_v7/exchange-calendar-20260916/calendar.json \
  --policy docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json \
  --output nn_meta/validation/v7-ordinary-actions-20260917
```

Use a new immutable output name on rerun. The independent consumer verification
source is retained as `verification.source.txt` in the consumer artifact.
All launched commands finished. No acquisition, V6 modification, deployment,
full research campaign or training launch occurred. The next work remains
6-1's identity/complex-action/no-event and held-position integration.
