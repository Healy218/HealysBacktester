# V7 dated hours and execution-path discovery — September 27, 2026

Dated regular-session rules now resolve every frozen entry root/date. A complete
first-leg envelope census and an actual replay/capture/resume pilot are also
implemented. V7-3 remains open: this is not full execution coverage, a complete
storage forecast, or training readiness. All original freezes remain intact.

## Historical regular hours

The sealed `v7-dated-hours-20260927` rules cover 576 selected option roots from
2022-03-15 through 2026-09-23. The audit resolves all 301,213 frozen root/date
pairs across 591 securities: 275,004 ordinary closes and 26,209 late closes,
including 2,370 early-close pairs. All 18 in-scope effective-date transitions
passed before/after checks. Forty roots have explicit exception histories.

The declaration is `docs/specs/V7_DATED_OPTION_HOURS_20260927.json`. Thirteen
previous Nasdaq captures plus sixteen follow-up exchange sources remain local
with immutable responses and receipts. Rules reconstruct history from historical
baselines and effective-date notices, carrying a rule until superseded. Reviewed
changes are assumed complete for this finite scope. This is not a daily historical
symbol-directory capture; today's late-close list is only a cross-check.

Examples include HYG/EWZ (2023-09-18), TLT (2024-08-12), FXI/LQD (2024-11-01),
IYR (2024-11-11), SLV (2025-02-18), IEF (2025-05-27), KWEB (2025-05-30),
SMH/SOXX/SOXL (2025-08-25), XOP (2025-09-24) and IBIT (2025-11-10).
Historical baseline evidence includes the 2013 CBOE ETF-options presentation,
2017 listing/class notices, GLD's 2021 notice, and the separate VXXB listing
and VXX rename history. These avoid confusing today's VXX with its predecessor.

The contradictory year in Nasdaq's IVV notice is resolved by MIAX's explicit
April 21, 2026 effective date. IVV is absent from the 576 selected roots, so it
changes no current demand. The corroborating response is nevertheless bound.

Primary examples:
- [MIAX IVV effective-date notice](https://www.miaxglobal.com/alert/2026/04/20/miax-exchange-group-options-markets-corporate-action-alert-etf-closing-time-1)
- [Nasdaq HYG/EWZ notice](https://www.nasdaqtrader.com/MicroNews.aspx?id=OTA+20023-35)
- [Nasdaq TLT notice](https://www.nasdaqtrader.com/MicroNews.aspx?id=OTA+2024-48)
- [CBOE historical ETF-options presentation](https://www.interactivebrokers.com/webinars/WB_1635_CBOE_Options_ETFs.pdf), slide 10, late-closing class list.
- [CBOE SVIX/UVIX notice](https://cdn.cboe.com/resources/product_update/2022/Change-to-Daily-Closing-Time-for-Options-on-Certain-Exchange-Traded-Products_UVIX_SVIX.pdf), page 1, April 25, 2022 change.

The compact reader preserves the captured exchange calendar, handles DST,
early closes and non-session expirations, and refuses unreviewed roots/dates.
This finite history does not authorize extrapolating option cutoffs beyond
2026-09-23; later expirations encountered by replay need an explicit scoped
extension. The entry-hours audit does not certify those future cutoff inputs.

## Full first-leg envelope and storage sensitivity

All 591 checkpoints completed. After removing the five approved exact entry
blackout pairs, 98,349,826 selected clock/target outcomes cover 1,057,177 contracts.
Conservative first legs, from first selection through expiry/history end, span
5,867,251 potential contract/dates. Subtracting the original quote-request union
leaves 32,130,174.7 additional quote hours, about 8.48 times the existing covered
quote time within these envelopes. No held-option trade windows were invented.

These are possible holds, not realized paths. Stops and signal exits shorten
paths; subsequent rolls and physical delivery can add different inputs. Four
blackout dates could intersect earlier-opened first legs (VFC, MSTR, RH, FANG).
Their actual held-path impact still requires replay. CMA has no such earlier
first-leg crossing in this census. The exact five-date exclusion policy is
unchanged; earlier closed paths remain valid.

Transferring the measured packed pre-entry quote byte rates by year and security
demand quartile yields these **sensitivity scenarios for additional first-leg
quotes alone**:

| Held/entry byte-rate ratio | Additional bytes |
| --- | ---: |
| 0.25 | 257.39 GB |
| 0.5 | 514.77 GB |
| 1.0 | 1,029.54 GB |
| 2.0 | 2,059.09 GB |

This is not a statistical confidence bound or the final required storage. It
excludes new roll contracts, stock data, metadata, new routing overhead,
assembly/training and recovery. It demonstrates why blanket acquisition of
every possible held interval is unsuitable under the existing caps. Actual
replay-driven capture and representative realized-path measurement are needed.
MRHA's approximately 693 GiB free does not raise the 250 GB acquisition or
640 GB total-project caps; the 20 GiB local reserve also remains in force.

## Actual replay and restart proof

`execution_frontier.py` wraps the unchanged replay, quote, reference and hours
consumers. The first uncaptured input records an exact request and stops further
reads on that path. In particular, a missing earlier mark cannot silently permit
a later stop/exit/roll branch. Genuine fully captured but stale/empty markets
remain explicit unavailable/unfilled outcomes. An approved reference blackout
remains a separate excluded path with its legitimate partial ledger.

The source-bound pilot uses five original proposal rows and selectors, one each
for DIS, ABBV, NVDA, VKTX and FUTU across 2022–2026. It does not substitute a
synthetic horizon or a different contract. Rounds r0–r12 retain all five paths.
The first two capture rounds acquire only exact missing intervals and reuse
existing purchase windows where possible. Later rounds prefetch at most ten
minutes per same-contract/session frontier, with a one-quote-hour batch cap.
Prefetch bytes are acquisition overhead, not proof that the path consumes them.
No missing reference, stock quote, identity boundary or session is guessed.

| Path | Latest result | Fills | Observed marks |
| --- | --- | ---: | ---: |
| DIS | Completed midpoint-stop label | 2 | 6 |
| ABBV | Completed midpoint-stop label | 2 | 16 |
| NVDA | Next held-mark capture pending | 1 | 142 |
| VKTX | Next held-mark capture pending | 1 | 46 |
| FUTU | Next held-mark capture pending | 1 | 39 |

All 60 earlier-fill/mark prefix comparisons and all 21 completed-label comparisons
pass across the twelve resumes. Completed results remain identical as unrelated
captures are added. Sparse captured marks remain visible; these five purposive
cases are neither a representative volume sample nor investment performance.
The twelve completed new packs total 527,812 bytes, including reused records and
metadata. Failed sandbox transport attempts retain separate partial/attempt
receipts and remain charged. The acquisition ledger ends at 69,019,919,439 bytes,
with no outstanding reservations. No capture or replay process remains running.

## Artifacts and continuation

All paths below are under `nn_meta/validation/` unless stated otherwise:

- `v7-dated-hours-20260927` and `v7-dated-hours-audit-20260927`.
- `v7-execution-envelopes-20260927` and its 591 sibling `.checkpoints` stores.
- `v7-execution-volume-sensitivity-20260927`.
- `v7-execution-discovery-20260927-r0` through `-r12`.
- `v7-execution-sample-index-20260927` and `-r1` through `-r12`.
- `v7-execution-prefetch-20260927-r3` through `-r12`.
- `v7-execution-pilot-audit-20260927`.
- New immutable packs: `nn_meta/data_v7/execution-frontier-20260927-r1` through `-r12`.

Continue from r12 with a new r13 output. The three unresolved reads are recorded
in r12/report.json and exact uncovered intervals in r12/capture-requests.json.
Use `plan_v7_frontier_lookahead.py` only for the bounded pilot; use
`advance_v7_execution_frontier.py` to acquire its sealed plan, then
`discover_v7_execution_paths.py` to replay. Each CLI derives its repository root.
All producer source hashes are now bound; preserve them and use a new version
when changing behavior.

Full-scope dated references, realized execution/roll/stock demand, a representative
complete-path storage forecast, full packed scheduling, physical/shared-capital
integration, assembly/folds, resource/recovery feasibility and final readiness
remain open. The existing untracked assembly/dataset adapters were not modified.
Their production packed integration is not implied by this pilot. V7-3 and
training readiness stay incomplete.

Validation: nine focused tests cover dated boundaries, scope/drift, exact fill
windows, stop-on-missing-mark behavior, reference gaps versus blackouts, stock
expiry and roll frontiers, envelope overlap/resume, and bounded prefetch. Full
suite results are recorded in the companion verification JSON.
