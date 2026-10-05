# ETFE joined diagnostic schema — October 5, 2026

**ETFE-2.joined-schema** joins the verified fresh ETFE causal, option-feature r1,
TV-feature and remaining-feature studies. Preserve all 458,133 original January
18–19 events across nine ticker/timeframe scopes. This is a bounded diagnostic
schema/lineage milestone, not an admitted dataset, execution or training run.

## Identity and matrix contract

Use isolated `etfe-joined-20261005-r0`. Bind the four exact predecessor plans,
COMPLETE/independent/resume receipts, all scope inputs, remaining shared/daily
receipts, registry, binding amendment, join/audit source and package versions.
Never edit earlier consumers or relabel their artifacts. The derived schema ID
is `etfe-joined-diagnostic-v2`, explicitly an unadmitted diagnostic container.

Each chunk has four immutable Parquets with matching row order:

1. `matrix`: the 221 canonical field names in registry order, then their 221
   `missing__<name>` indicators. Values float64, masks uint8. No metadata, reasons,
   clocks or outcomes enter this 442-column matrix. No filling/scaling/casting
   to model float32, labels or learned preprocessing occurs.
2. `reasons`: 221 reason columns in the same value order. Copy predecessor
   reasons, with `no_prior_date_observed_candidate` for a null option-window
   membership. Shared technical fields previously lacked field-specific reasons;
   derive observed, incomplete-bin or history/denominator-unavailable explicitly.
3. `availability`: 221 UTC nanosecond int64 columns; -1 only for a missing value.
   Every finite value must have a known modeled clock no later than decision.
4. `rows`: every original event field and ordinal; logical row ID; selected
   contract null and actual DTE missing; acquisition candidate separate; bar-open,
   signal/context/TV/window pointers, event payload SHA, missing count and false
   model-feature admission. Original entry eligibility remains false.

Logical ID is SHA256 of compact canonical JSON `["etfe", ticker, variant_id,
direction, signal_close_ns, target_dte, null]`. Null is the selected contract,
not the acquisition candidate. Assert uniqueness across the complete study.
The PLAN owns source-file hashes; schema field ownership plus row pointers
provides cell-to-component-to-raw lineage. Target replicas keep distinct IDs.

## Source alignment and clocks

- Technical fields: exact closed-stock-bar clock and raw spot; retain thirteen
  shared fields. `ma_gap`/`px_vs_fast` come from the remaining component's verified
  per-variant signal table, including its 10/30 defaults for other families.
- Signal identity/age: exact variant, strategy, direction and signal close, with
  the original full-prefix recurrence preserved. Clock is signal close.
- Catalog: exact variant key, family and timeframe; clock is decision close for
  mathematical parameter definitions, not a historical metadata observation.
- Daily context: exact ticker and decision-session date; supplied next-open
  availability must be <= decision. Never search forward or use a later day.
- TV: exact supplied observation ordinal and signal-close clock. No positional
  fallback across timeframes or ticker scopes.
- Dated contract/sector fields: copy the original event-ordinal missingness.
  No target-DTE substitute, acquisition-candidate admission or sector inference.
- Option windows: exact window key, candidate symbol, signal/timeframe, half-open
  bounds and scope flag. Null membership is retained. Conservative clock upper
  bound is feature-window end +1 second under the predecessor's final-vintage
  availability model. Current finite observations passed that component's policy;
  this is not newly established provider publication timing.

Reject missing/duplicate source keys, mismatched ordinals/identity, changed source
masks/dtypes, infinity, inconsistent missing reasons, future/unknown finite-value
availability and unexpected predecessor admission. Canonical column order and
schema fingerprint are strict. Every joined row stays model-feature-admitted=false.

## Bounded writes, recovery and acceptance

One sequential writer, chunks of at most 5,000 rows, 2 GiB study-root ceiling,
30-minute active run ceiling; preserve the existing max(100 GiB,20%) disk and
max(2 GiB,20%) RAM reserves. A payload attempt has unique paths. Only a published
chunk receipt commits its four files; orphan attempts never become completed
chunks. Resume verifies every existing receipt/payload hash and ordinal interval.
Measure actual RAM, disk and compute; these are not integrated training forecasts.

For every actual chunk, split its event range at a different boundary, rerun
the join and require byte-value equality for all four tables. Exercise an actual
one-chunk stop/resume. Unit fixtures cover null candidates, identities, keys,
variant/timeframe checks, future clocks, masks/reasons/dtypes, schema order,
repartitioning and committed-payload tampering.

An independent audit aligns sources using natural keys rather than the joiner's
ordinal links: variant/direction/close for signals, ticker/day for context, close
for TV/stock, and candidate/close/timeframe for option windows. Compare every
value, mask, reason and availability exactly; check every original row field,
logical ID, ordinal/pointer and source hash, plus complete chunk coverage and
per-field missing counts. This reuses already-audited numerical components; it
is not a new independent native-indicator or economic evaluation.

Exit: joined diagnostic schema and bounded row-level lineage validated, current
owner documents updated, evidence retained. Dated actions/identity/surface/session/
publication, usable history, full phase-B/C demand, admitted dataset/execution and
integrated ETFE-4.pilot remain open. No live/paper orders or training are authorized
by this component completion.
