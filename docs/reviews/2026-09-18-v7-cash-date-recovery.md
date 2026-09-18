# V7 6-1 recovery and primary cash-date continuation

The interrupted session had pushed `086eb39`, but left eight reviewed IBM/TGT/PNC
cash-date events and their 4,381-event verification uncommitted. It also left the
January 2025 closure exception, exact historical producer snapshots, and v2 CLIs
partially integrated. The September 17 HANDOFF still described 4,373 events.
Recovery preserved those files and all unrelated V6/assembly changes.

## Completed evidence

Rechecked the eight original reviews against saved issuer content (Target PDF
page 1 visually). Added 40 exact primary reviews from existing captures, including
MPWR's December 2023 8-K, whose PDF starts with whitespace. PDF pages inspected:
Alphabet 3, HCA 3, HPE 2, IBKR 1, LVS 3, Morgan Stanley 8 (printed 4), MPWR 2.
No network acquisition was needed.

- `docs/specs/V7_CASH_DATE_REVIEWS_20260917.json`: eight recovered reviews.
- `docs/specs/V7_CASH_DATE_REVIEWS_20260918_R2.json`: 40 additional reviews.
- `nn_meta/validation/v7-stock-cash-dates-20260918-r2`: **4,421 entitlements**, all
  4,381 predecessor objects unchanged. The original 4,337 remain unchanged.
- `nn_meta/validation/v7-stock-cash-dates-verification-20260918-r2`: verifies every
  entitlement's source, amount, identity, clocks and captured settlement coverage;
  the actual no-inventory portfolio consumes all 4,421 without creating cash.
- `nn_meta/validation/v7-dividend-closure-20260918-r2`: full original-record census,
  **437 uncompiled cash groups +7 date cases =444 remaining dividend items**.

All 4,527 price actions, 4,428 cash price actions, and 586,876 admitted history
sessions remain unchanged. The original provider-record partition remains
10,428 =9,079 price-action records +93 unrelated +7 rename +1,249 pending.
This work resolves held-cash dates; it does not change chart publication claims.

## Exact exception and historical producers

The retained Nasdaq ETA2025-1 notice explicitly defers January 9, 2025 ex-dates
to January 10 while January 9 remains a settlement date. Original INTU, ORCL and
MA notices retain January 9 record dates. `cash_date_exceptions.py` allows only
those three symbols, those exact dates, the pinned notice hash, and a calendar
with January 9 closed. Both compiler and runtime require the finite exception;
the compiler additionally binds issuer and exchange evidence. Ordinary rules
still reject arbitrary record-before-ex dates. Funded-ledger fixture tests prove
accrual, non-spendable receivables, subsequent release and idempotence; they are
not historical funded fills in those securities.

PNC's explicit next-business-day payment clause selects the reviewed effective
payable date. Other reviewed nominal dates retain the authorized first regular
open strictly after pay-date model. A weekend date alone does not justify moving
all providers to a common date. Common/preferred and HSY common/Class B amounts
were distinguished explicitly.

`producer_versions.py` maps only two exact prior cash-producer path/hash pairs
to byte-identical archived Python sources. Historical receipts are preserved;
new outputs bind those original bytes plus current executing producers. Unknown
source changes still fail. Use the v2 compile/verify/census scripts with this
lineage; old CLIs can correctly reject a changed current producer hash.
The snapshots are provenance evidence, not a claim that older code implements
the new exception, and not a blanket cache migration waiver.

## Remaining date work and limits

Seven exact cases remain: CMA 2023-09-14 and 2023-12-14; FIX 2023-05-17;
QQQ 2023-12-27 and 2024-03-18; PG 2024-04-18; RILY 2024-05-23.

- CMA/FIX need the exact historical payment evidence.
- QQQ December's saved OCC #53847 states a special distribution and strike
  adjustment. Inspect its full PDF visually and integrate its option semantics;
  do not label it an ordinary dividend merely to use the current date compiler.
  The March QQQ date dispute still needs usable issuer evidence.
- PG's saved notice says payable on or after May 15; RILY says on or about June
  11. Those qualifiers have not been silently converted to exact posting dates.
  Resolve their actual terms under the accepted reconstruction model, or record
  any genuinely necessary policy extension explicitly.

The 437 uncompiled groups retain their prior split: 328 unit/term, 47 combined,
34 mismatch, 14 single-provider, 11 selected-identity, 3 adjacent-continuity cases.
Identity exceptions, complex actions, option deliverables and complete held
lifecycles remain. **6-1 stays open; 6-2 stays queued.** No full dataset/training,
V6 policy change, deployment or performance verdict occurred.

## Validation and storage

Full suite: **2,246 tests +18 subtests passed**, 19 warnings, 129.84 seconds,
exit 0. Receipt: `nn_meta/validation/v7-recovery-tests-20260918`. The 21 new
focused tests cover date/source rejection, funded exception accounting, and
exact producer preservation. Actual compile, consumer verification and census
CLIs also succeeded. Inherited captured funded AAPL evidence is retained;
no new historical funded position or completed strategy outcome is claimed.

New September 18 date/census/test outputs total 52,065,145 bytes (including
retained intermediate r1 outputs). No new download bytes in this session.
Observed quota ledger: 68,907,498,073 bytes, zero reservations; 458.69 GiB disk
free. This updates the stale handoff's quota observation without attributing its
increase to this session. Total-project budget/forecast remains necessary before
bulk acquisition or full stores. Preserve existing artifacts and the 100 GiB
reserve; maximum four outer workers and one inner thread remain in force.
