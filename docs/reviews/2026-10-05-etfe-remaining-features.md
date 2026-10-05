# ETFE remaining feature components

Completed **ETFE-2.remaining-components** within its declared component scope:
**100 remaining registered fields** now have implementations, alongside
variant-specific MA projections. The component census reconciles all **221
registered field names**, without closing joined-schema or input admission.
[Definition](../specs/ETFE_REMAINING_FEATURES_20261005.md),
[machine receipt](2026-10-05-etfe-remaining-features.json).

Selected root: `nn_meta/validation/etfe-remaining-features-20261005-r0/`.
Plan SHA256: `8fe1d85439c8458cbe86d166f6b70ec23be4f4a5baca66cd2e04b94885445145`.
Inputs are selected fresh Alpaca ETFE artifacts and the independent ETFE catalog.
No old market data, metadata, model arrays or runtime selectors were inputs.
No downloads, execution simulation, labels, training or deployment occurred.

## Implemented components and real observations

| Component | Fields | Evidence scope |
| --- | ---: | --- |
| Strategy/timeframe/parameter identity | 77 | All 8,451 catalog variants, 650,727 value cells |
| Direction and signal age | 2 | 152,711 distinct signals, all 458,133 original event links |
| Actual contract DTE/moneyness | 2 | Dated-evidence API and synthetic guards; real fields withheld |
| Sector identity | 9 | Dated-evidence API and synthetic guards; real fields withheld |
| Daily stock volatility/beta | 3 | 691 sessions × three tickers, explicit missing history/gaps |
| Daily option context | 7 | Synthetic complete-surface formulas; real fields withheld |
| **New total** | **100** | **Raw diagnostics or explicitly missing; none admitted** |

The two MA fields already present in the shared stock component now also have
correct per-event variant projections: each MA strategy's actual fast/slow
windows, and 10/30 defaults for other families. These are overrides, not two
additional model fields. Static arrays and signal arrays are factored without
losing any original variant/direction/target membership.

Full-prefix replay found **35,378 observed signals whose previous same-variant/
direction signal predates January 18**. Their age now uses the January 2 prefix;
starting the counter at the observation window would incorrectly lose that
history. Target replicas never advance the signal counter. Save every native
signal position, including pre-pilot occurrences, for independent inspection.

The daily table has **2,073 rows / 20,730 cells**: 5,588 finite raw-stock context
values and 15,142 explicit missing values. The latter include all 14,511 option
context cells, plus 631 stock-context cells with insufficient complete rolling
history or variance. The twelve known VOO missing minutes affect ten sessions;
those ten daily closes are withheld and rolling gaps remain in the calendar.
All completed-day context is available at the next regular open, never before.
Raw stock values remain unadmitted pending dated action reconstruction.

## Formula correction and missing evidence

The original registry mistakenly encoded Setup maximum holding bars and ATR
stop multiplier as categorical identity comparisons. The fresh catalog has
numeric values **60** and **1.2**. A versioned
[binding amendment](../specs/ETFE_FEATURE_BINDINGS_20261005.json) corrects those
previously unimplemented fields, restates actual DTE/5 under the approved 0–5
purchase rule, and clarifies structural missingness for non-Setup parameters.
The original registry and all completed predecessor artifacts remain unchanged.

DTE/moneyness require a dated **selected** contract, not an acquisition candidate
or target DTE. All nine sector fields require dated identity. All eleven remain
missing on every real pilot event. Synthetic tests verify 0DTE, the five-day
boundary, unknown/future/ambiguous identities and direction/right consistency.

The seven option-context formulas include near/far BS-proxy IV, term slope,
five-session change, put/call volume ratio, SPY IV and RV-minus-IV. They use the
predeclared 1–45 DTE context window, last fresh closing VWAP, .20 premium filter,
ATM band, fixed rates, bounded bisection and explicit availability. Complete
synthetic surfaces exercise values, clipping, missing denominators and rejection.
**Real option-surface numerical acceptance remains open:** raw transport/current
expired listings do not supply dated complete catalog, contract and capture
proof. No proxy value or aggregate is invented to fill those missing inputs.

## Validation, recovery and resources

**157 focused ETFE tests passed**, including fourteen new tests. Every catalog
field, every signal-age/MA value, all daily context values, missing masks/reasons
and all 458,133 event links passed independent reconciliation. A supplemental
source-bound audit independently reconciled all 2,073 daily input rows to the
original one-minute grids, including the ten invalid daily closes.

All nine ticker/timeframe scopes passed actual full-catalog truncated-prefix
and changed-batch-width checks. Three full-window stock-context prefix/future
checks passed; synthetic tests cover option-context next-open/future behavior.
Numerical comparisons retain rtol=atol=1e-12. Native signal kernels are reused
mathematics; this is not independent exported Pine parity proof.

Actual one-scope stop/resume preserved **nine completed files**, including shared
outputs, and computed the remaining eight scopes. Component compute totaled
**51.32 seconds**, peak RSS **1,387,171,840 bytes (1.29 GiB)**, root footprint
**18,252,538 bytes**. The [evidence ZIP](2026-10-05-etfe-remaining-features-evidence.zip)
contains 69 metadata/source/audit members and hashes for 21 Parquet and nine
compressed native-position payloads. ZIP SHA256:
`2719ed0327d22dd3d264277bae9cabdc50df7fbad9d5ba99946a4752fc906fe8`.

Next: join all components in the declared 221-value/221-mask order and verify
row/availability alignment, resolve dated identity/actions/surface/session evidence,
then complete full phase-B/C demand and the integrated ETFE-4 execution/dataset/
training smoke pilot. Usable history, dataset freeze and training remain open.
