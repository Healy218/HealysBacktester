# ETFE remaining feature components — October 5, 2026

Implement the 100 remaining registered fields: ten daily-context fields and
ninety event/contract/sector/parameter fields. Also replace shared 10/30 MA
projections with catalog-specific MA windows where the event's family is MA.
This is **ETFE-2.remaining-components**, a bounded component milestone permitted
by ROADMAP's first-run sequence; full schema integration/admission is separate.

## Versioned formula correction

`ETFE_FEATURE_BINDINGS_20261005.json` binds the frozen original registry and
corrects two previously unimplemented formulas. `param_setup_max_bars` and
`param_setup_stop_atr` are numeric catalog parameters, not comparisons of the
Setup identity to the strings `max_bars` and `stop_atr`. DTE/5 restates the
approved October 4 successor. The six Setup identity one-hots are structurally
missing outside that family, consistent with the registry's absent-parameter
missingness rule. No earlier source-bound result is rewritten or invalidated.

## Static and event features

Bind the selected fresh ETFE v4 catalog: 8,451 timeframe/parameter records,
25,353 ticker combinations, twenty families. Factor the 77 static values by
variant: twenty strategy flags, three timeframe flags and 54 parameters.
Absent parameters remain NaN with `structural_absence`; malformed identity fails.
Keep all 458,133 January 18–19 logical events and original event ordinals.

Replay all entry signals from the fixed January 2 stock prefix. Count completed
chart positions since the preceding same-variant/direction signal; use log1p
of that count, and NaN for a first-ever prefix signal. Targets do not constitute
new signal occurrences. Save every native signal position, including those
before January 18, for independent age/membership reconciliation. Recheck a
real truncated prefix with different batch width at every ticker/timeframe.
Direction is the known call/put intent (long/short), not a selected-contract
admission claim. MA diagnostics use that variant's fast/slow, otherwise 10/30.

DTE and moneyness require the actual dated selected contract and positive raw
spot, not target DTE or an acquisition candidate. Sector one-hots require dated
security identity. Typed evidence includes effective interval, publication clock
and evidence hash; future/ambiguous evidence cannot pass. No such selected
contract/sector evidence is available for this pilot: retain all eleven fields
as explicit missing values, without substituting current discovery metadata.

## Daily context

Reduce all 691 fresh stock-calendar sessions for SPY/QQQ/VOO from the existing
verified expected one-minute grids. Any missing minute invalidates that day's
close; never compress the session sequence. Compute 5/21-session sample standard
deviation of log returns times sqrt(252), and 60 paired simple-return sample
covariance divided by SPY sample variance. Zero variance is missing. Context
for a completed day first appears at the next regular open; no current-day
close or incomplete rolling history enters it. Raw closes yield expressly
unadmitted diagnostics until dated action adjustment is available.

Implement seven option-derived daily formulas under the original definitions:
1–45 actual calendar DTE; fresh closing minute end within the last sixty seconds;
closing VWAP at least .20; abs(log(K/S)) strictly below .01 for ATM IV; fixed
r=.0425/q=.012 European BS proxy; sigma [1e-6,5], 100 bisections, price tolerance
1e-8. Reject out-of-bounds prices rather than clamp. Median near/far IV uses
1–20/21–45 DTE; retain raw and clipped [0,5] put/call session-volume ratio.
Context never includes 0DTE (purchase scope still does). Derived fields use
same-prior-session SPY IV, far-minus-near, exact five-session near-IV endpoints
and prior RV21 minus near IV. No forward-fill.

The surface API requires dated catalog/capture/terms proof with exact symbol,
underlying/session identities and publication clocks. Late required observations
withhold the aggregate. Complete capture alone is not complete dated evidence.
The real pilot has no such proof, so all seven option-context fields remain
missing with an explicit coverage reason. Synthetic complete surfaces exercise
the formulas and rejection paths; this is not real-surface numerical acceptance.

## Evidence, resource limits and exit

Isolated root `etfe-remaining-features-20261005-r0`; bind fresh causal/TV roots,
selected normalization and context-capture seals, exact source/package versions,
catalog, registry/amendment and this definition. Preserve source snapshots.
Single sequential writer, 1 GiB root, 30-minute active compute limit and existing
100-GiB/20%-disk and 2-GiB/20%-RAM reserves; no worker pool or new capture.
Factor static, daily and signal arrays, but preserve every logical event link.

Independent audit checks every static value/mask/reason against catalog, every
signal age against full native positions, MA values against direct window means,
all context values against scalar rolling calculations, and every logical link
and withheld field. Synthetic tests cover dated identity, 0/5/out-of-range DTE,
missing intervals, proxy inversion, thresholds, clipping, next-open clocks and
prefix/future invariance. Real prefix/batch checks cover all variants; actual
one-scope stop/resume retains completed bytes. Record peak RAM/disk/compute.
This closes component implementation and its declared real/synthetic evidence
only. Full joined schema, dated source admission, full demand and integrated
execution/dataset/training pilot remain open; model-feature admission is false.
