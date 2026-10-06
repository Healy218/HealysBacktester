# Handoff — October 6, 2026 — Full discovery and dated-input validation

## Focus and result

User selected full coverage and dated-input validation. Completed
**ETFE-1.full-discovery** across the full calendar, plus full-window Alpaca
announcement capture. [Review](docs/reviews/2026-10-06-etfe-full-coverage.md),
[machine receipt](docs/reviews/2026-10-06-etfe-full-coverage.json).
Universe stays SPY/QQQ/VOO; 0–5 DTE purchases/rolls including qualifying 0DTE,
1–45 DTE context, completed-minute option VWAP, fixed October 2 price end.

- Six range queries / 455 successful GETs / 452,347 unique contracts. All
  6,300 calendar expiry/status partitions have complete transport; 4,756 are
  empty current observations, not proven historical nonexistence.
- Every one of 45,470 prior symbols matches stable identity. All raw/typed
  occurrences and 2,073 session counts reconcile independently. Five `1SPY`
  identities retain missing parsed fields/flags; no historical admission.
- Gross envelope: 14,049,776 symbol/session pairs, 1,832,006 purchase pairs,
  141,489 session-batch bar requests before pagination/reuse. These are not
  exact phase-B/C demand. Raw payload 321.29 MB, typed payload 41.20 MB.
- All current contracts lack historical effective/available terms clocks;
  43,720 invalid/zero multipliers, 53,634 pre-transition expiries with T+1 text.
- Full announcements: 36 HTTP 200 queries / 33 dividends, eleven per ETF,
  all with declaration dates before ex-date; all prior in-window actions match.
  QQQ 2024-03-18 payable conflicts: April 30 announcement versus May 1 data API.
  Declaration dates do not prove original intraday availability/revision history.
- Rejected announcement r0 preserved: documented Reorg caused 36 HTTP 422s.
  Selected v2 uses four accepted types and stops on non-200. Six initial dated
  controls are retained. Do not repeat these completed captures.
- Actual restart preserves seven first-page files, 1,828 complete raw files,
  917 normalized files and 76 announcement files; completion makes zero GETs.
  All 320 ETFE tests pass, two existing protobuf warnings. No process remains.

## Stopping point and next actions

Full market acquisition, dated admission, usable start, freeze and training
remain open. This is completed discovery transport and a failed dated-input
admission check with concrete evidence; no scientific label or real execution.

1. **ETFE-1.demand:** derive exact full-window signal/context/trade and holding/
   roll/exercise window unions from the new census. Budget raw, typed and
   temporary storage. Earlier blanket quote scenario was 1.32 TB; do not launch
   a whole-calendar quote pull or mistake the gross envelope for exact demand.
2. **ETFE.provider-contract / action-timing / history-boundary:** resolve dated
   terms/adjustments/class hours, historical SIP size units, official exercise
   references and QQQ payable conflict. Keep original/revision availability
   explicit; no current metadata backdating or zero-multiplier replacement.
3. **ETFE-4.pilot:** integrate admitted real features/execution/isolated labels
   and recovery/resource evidence before full build/freeze and training.

## Selected artifacts and constraints

Raw: `nn_meta/data_cache_etfe/alpaca-fresh-20261005-full-discovery-r0/`.
Typed/census: `nn_meta/validation/etfe-full-coverage-20261005-r0/`.
Announcements: `nn_meta/data_cache_etfe/alpaca-fresh-full-announcements-20261006-r1/`.
Earlier frontier r2 is retained as a provenance/density baseline.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#full-discovery-and-dated-input-census).
Evidence ZIP indexes 2,915 files; payloads remain in isolated local roots.
Bound sources cannot change in place. Preserve unrelated dirty V6/V7 work.
[Previous handoff](handoff-history/HANDOFF-2026-10-06-before-full-coverage.md).
