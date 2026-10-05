# ETFE option trade/bar feature components

Implemented all **ten registered option trade/bar formulas** and exercised them
on the fresh January pilot inputs. The selected successor is
`nn_meta/validation/etfe-option-features-20261004-r1/`.
[Component definition](../specs/ETFE_OPTION_FEATURE_PILOT_20261004.md),
[machine receipt](2026-10-04-etfe-option-features.json).

Every output is an explicitly named `diagnostic__` value with a uint8 missing
mask and reason. **No output is admitted as a model feature.** Historical
selection, dated option hours, condition applicability, publication timing and
coverage remain unresolved. No market-data download, execution, labels or
training was performed in this study.

## Complete census and missingness

The consumer preserves **458,133 logical events** from all nine ticker/timeframe
scopes. The 195,435 candidate links factor into **4,739 distinct feature windows**;
262,698 events still have no prior-date observed candidate. Original event
ordinals and hashed source files preserve variant/direction/target membership.
No contract is reselected because its feature data is inconvenient.

| Window result | Distinct windows |
| --- | ---: |
| All ten diagnostic values available | 1,803 |
| Some values available | 192 |
| All values missing | 2,744 |
| **Total** | **4,739** |

The 1,803 fully populated windows serve **68,862 logical candidate links**;
this is a diagnostic-data count, not eligible trades or model-ready rows.
Thirty windows / 3,387 links extend outside the pilot stock-session scope and
remain missing pending dated option-hour evidence. Missing trade observations
affect 2,714 windows; missing bar observations affect 2,717. Those family-level
counts overlap and must not be added together.

Unknown equal-time ordering masks signed/classified-volume fields in **189
windows / 8,065 logical links**. Order-independent values remain usable as
diagnostics. A final timestamp with conflicting prices also masks VWAP-versus-
last; that rule is tested, though no real pilot window triggered it. Three
windows have trade calculations but missing bar fields, matching the previously
recorded bar gaps. Empty provider responses are not converted to zero-trading
features. Synthetic dated no-trade evidence exercises the legitimate zero-count
case separately; no such evidence was supplied for the real study.

## Semantics and independent checks

The ten formulas cover trade range, population size coefficient of variation,
bar fraction/age/rate, trade count/volume rates, VWAP-versus-last and tick-rule
signed/classified-volume fractions. Condition filtering follows the frozen
research allowlist, with excluded counts/volume retained in audit metadata.
VWAP divides by eligible trade size, not provider bar volume. Tick signs start
fresh inside each window; leading equal-price prints remain unclassified.

Windows are exactly `[t-(m+1) minutes,t-1 minute)`. Default research availability
is event/end +1 second; explicit later availability masks the affected family.
Capture timestamps are not publication clocks. Invalid required observations,
repeated native IDs and conflicting bar vintages fail closed. No-ID occurrences
are retained, and duplicate occurrence identities are rejected.

Every calculated real window passed reversal of input occurrences and injection
of extreme future records, with unchanged masks/reasons and numerical agreement
at rtol=atol=1e-12. A separate implementation using stable scalar sums independently
recomputed **all values, missing masks and reasons**, and verified **all logical
links**, exact window bounds and payload hashes. **129 focused tests passed**,
including hand-worked formulas, condition exclusions, native-ID revisions,
missing/invalid data, delayed availability, verified-empty fixtures, 1/5/15-minute
future boundaries and ambiguous ordering.

The first scope completed, then the requested scope limit stopped the process.
Resume preserved its three output/receipt hashes and computed the remaining
eight scopes. Successor component compute totaled **2.26 seconds**, recorded
peak RSS **0.67 GiB**, root footprint **4,384,713 bytes**. These are bounded
component measurements, not integrated execution/build/train forecasts.

## Rejected first run and selected successor

The independent audit rejected r0: VWAP-versus-last was approximately
-1.46082e-12 basis points where the independent result was zero, just outside
the predeclared tolerance. The producer's vector dot-product accumulation was
replaced with a stable weighted sum. The tolerance was **not relaxed**.
A constant-price regression fixture reproduces the original edge case.

The r0 plan, source snapshots, outputs and AUDIT_REJECTION are preserved.
Its producer COMPLETE receipt does not imply audit acceptance. The new r1 root
was prepared from the corrected source and passed the unchanged audit. This
rejection affects only the new option-feature component r0; prior capture,
normalization, causal-signal and demand evidence remains complete.

Selected plan SHA256:
`808c721bf5bb6583e84e0b9b104f06961b6ed9ab03f161f72d05dcdb4f9c4183`.
The [evidence ZIP](2026-10-04-etfe-option-features-evidence.zip) contains 50
metadata/source/report members and hashes for 36 local Parquet payloads across
both roots. Payloads remain local. ZIP SHA256:
`7fdb06ad8806097867e2e35b80c1b70359d2727ea0bc761ae5acb13f58a39654`.

This closes **ETFE-2.option-trade-bar-components**. Full 221-field schema,
remaining TV/context/other feature components, dated admission, full phase-B/C
demand and integrated ETFE-4.pilot remain open. No scientific-history boundary,
execution readiness or economic verdict is inferred from this component result.
