# V7 item 6-1 — source routing progress and remaining admission choice

Item **6-1 remains open**. The retained Fiserv publication evidence now selects
FI on June 7, 2023 in the actual full security-history builder. The full census
has no ambiguous listed-source day. Corporate-action admission and held-position
lifecycle treatment are still incomplete; no later numbered item was started.

## Implemented and exercised

`compile_v7_source_routes.py` extends the existing alias artifact, retaining all
67 earlier reviewed routes and adding the exact FISV/FI overlap. Its output is
consumed directly by the unchanged `build_v7_security_history.py --aliases`
interface. The new compiler verifies retained publication bytes/receipts,
existing alias sources, exact dated identities, selected raw daily shard and
their source bindings. Different or absent FIGIs, missing observations, late or
naive publication clocks, duplicate reviews and source collisions fail.

The May 25 Nasdaq-distributed Fiserv announcement gives the expected June 7
NYSE/FI start. The June 7 NYSE announcement confirms completion at its displayed
7:28am EDT publication time, before the open. Both retained exact-day listings
have `BBG000BJKPG0`. The dated review is
`docs/specs/V7_SOURCE_ROUTES_20260917.json`; this is an explicit review of retained
content, not an automatic publication extractor. Original captures remain under
`nn_meta/data_v7/public-actions-20260916/fiserv-*-nasdaq-release`.

FI contributes 385 observed minutes and a raw close of $115.88. Missing minutes
remain missing. The five-session window selects FISV/FISV/FI/FI/FI and keeps one
identity span. No monthly membership is created, and no option deliverable,
corporate-action factor, held-position outcome or full feature admission is
inferred from this routing evidence.

Full history: **667,239 rows /591 securities /1,129 sessions**, 606 identity
spans (previously 607), eight ticker transitions (previously seven), 614,116
observed rows and zero ambiguous-source rows. The 666,110 other-security rows
retain identical data, excluding source-selection evidence hashes that correctly
bind the new alias receipt. All 67 existing alias rows are unchanged and their
new evidence hashes were independently recomputed. Fiserv's pre-transition data
and later raw facts are unchanged. Eligible-source comparison is unchanged:
339,454/339,640 match, with 186 exceptions.

## Reconciled exception scope

The existing 186 mismatches and 59 zero-bar sessions overlap on 53 sessions:
**192 distinct eligible exception sessions**, not 245. Of the 186 mismatches,
133 have observed stock data. An absent identity is therefore not generally an
absence of prices, and selecting those prices by ticker would bypass the very
identity gate being repaired.

| Captured discrepancy class | Sessions | Affected symbols |
| --- | ---: | --- |
| Detail/list endpoints disagree with membership FIGI | 104 | BLK, BOIL, COUP, DISCA, DKNG, MCD, RKLB, SIRI, TWTR, VMW, X, XOM |
| Both endpoints omit FIGI | 33 | CCL, SWTX |
| Detail 404 and absent listed identity | 49 | ATVI, DISCA, SGEN, TWTR, VMW, X |

Exact dates, observed-session counts and source receipts are retained in
`v7-6-1-routing-verification-20260917/identity_exception_groups.csv` and
`identity_exceptions.parquet`. These are unresolved consumer inputs, not newly
approved exclusions. Existing retrospective lifecycle explanations still cover
41 cash-merger, 14 stock-successor and four halt sessions. The held-position
paths still need executable entitlement/deliverable treatment; an explanation
does not supply a fill or settlement.

## Concrete ordinary-action admission choice — pending user answer

The saved action inventory has **4,506 matching single-event groups: 4,409 cash
and 97 splits**. This includes SPY's 36 provider records as 18 matching cash
groups. The inventory verifies terms, not historical publication vintage.
Eighteen Apple groups already have separate reviewed publications. The prior
whole-event compiler still consumes 40 records into 19 cash events, leaving
10,340 provider records unconsumed, including 213 complex records. Those record
counts must not be described as distinct unresolved events.

The user was asked to choose between the following standards. No answer was
received as of this checkpoint, so the existing strict standard remains applied.

1. **Explicit historical reconstruction assumption for ordinary matching
   groups.** Accept the two retained providers' matching terms for a unique
   cash/split group with verified units and dated security continuity, only
   from its effective session. Keep original IDs, capture dates, missing
   publication vintage and the assumption in the output. Do not claim a
   pre-event publication receipt. Existing reviewed corrections take precedence
   exactly once. This would require an explicit policy amendment and a separate
   evidence classification in the compiler; it is not implemented here.
2. **Retain individual pre-event publication evidence as mandatory.** Ordinary
   matching terms remain candidates until that evidence is supplied. Existing
   reviewed events keep their current treatment. This preserves the present
   stricter standard but requires substantially more targeted evidence work.

Neither alternative admits duplicate/combined records by sum, foreign or
unknown units, spin-off ratios as share deliveries, changed security identities,
or absent records as proof of no event. The other 524 simple groups and complex
records retain their specific review requirements. Complete no-event interval
coverage remains a separate prerequisite: Alpaca is process-date bounded, and
a missing provider counterpart is not negative evidence. The pending choice
does not settle that prerequisite or authorize additional issuer exclusions.

The question follows HANDOFF's requirement to make a material admission-policy
change explicit. It is not a request to approve the already authorized source
routing fix. Continue independent identity/lifecycle work while awaiting the
answer; do not infer consent from elapsed time.

## Evidence and reproduction

All artifacts are under `nn_meta/validation/` and retain `research_ready=false`:

| Artifact | Receipt SHA256 |
| --- | --- |
| `v7-source-routes-20260917` | `564bf17023ed420ab43bf75cb1a9671538bba6c5b99eed83ed2987791e68cec3` |
| `v7-security-history-20260917-routes` | `366c21f3359c2b21fffa243c445832160bc4e9fa2ea66770d7a2874f1d2a087a` |
| `v7-6-1-routing-verification-20260917` | `a5beea02e91aab8ec54098cf4691eade96fa8b800660208ac79b17e01e62b9d3` |

```bash
./venv/bin/python scripts/compile_v7_source_routes.py \
  --aliases nn_meta/validation/v7-gap-alias-resolution-20260915 \
  --reviews docs/specs/V7_SOURCE_ROUTES_20260917.json \
  --identities nn_meta/validation/v7-daily-identity-panel-20260916 \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --output nn_meta/validation/v7-source-routes-20260917

./venv/bin/python scripts/build_v7_security_history.py \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --identities nn_meta/validation/v7-daily-identity-panel-20260916 \
  --source nn_meta/data_v7/start-20220315 \
  --availability-calendar nn_meta/data_v7/exchange-calendar-20260916 \
  --aliases nn_meta/validation/v7-source-routes-20260917 \
  --output nn_meta/validation/v7-security-history-20260917-routes
```

Existing immutable destinations must not be overwritten; use new output names
when rerunning. Independent full comparison source is retained in the
verification artifact as `verification.source.txt`.

Validation: 20 focused tests passed. Repository suite: **1,987 tests +18
subtests passed**, 18 warnings, 124.14 seconds; log
`/tmp/v7-source-routes-suite-20260917.log`. No production source changed after
that suite. Initial test collection exposed a test import typo, corrected before
the passing runs. Initial full comparison correctly detected changed alias
receipt hashes; the final verification checks those hashes independently and
compares all remaining data. No acquisition, V6 modification, deployment or
training launch was performed.
