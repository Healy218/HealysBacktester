# Reference completion, exception review and separate V6 OOM — September 28

## Download and full census

V7 dated-reference capture completed successfully at **16:48:10 Central**.
Its systemd journal records a 1-GB memory peak and normal completion, not an
OOM kill. All **2,223,844** frozen planned contract/date responses were captured
or reused; 8,987 packs retain **2,120,051,077 bytes**. No restart is needed.

The independent full audit verifies exact demand membership, uniqueness,
coverage, raw row hashes, pack receipts and standard-contract checks:
`nn_meta/validation/v7-reference-reconciliation-20260928-full-r0/`.

| Raw audit disposition | Contract/date pairs |
| --- | ---: |
| Standard | 2,212,991 |
| Previously approved exact blackouts | 5 |
| Other HTTP 404 responses | 10,817 |
| Strict standard-contract rejections | 31 |
| Uncaptured planned pairs | 0 |

Capture is complete; reference admission and gate 7-3 remain open. Actual held
paths may request further dates. No missing terms, blackouts or returns were
invented to close this census.

## Twenty-two narrowly reviewed rename corrections

Twenty-two rejected responses use old underlying names with new option roots:
GAP/GPS (5), FISV/FI (5), XYZ/SQ (12). The following exchange notices were
retained and their terms visually reviewed:

- [BOX GAP notice, OCC 55037](https://boxexchange.com/assets/BOXOnnMemo206676.pdf):
  GPS→GAP effective August 22, 2024; unchanged option terms and 100-share delivery.
- [OCC 57608 hosted by MIAX](https://www.miaxglobal.com/sites/default/files/alert-files/FI__Symbol__Change_57608.pdf):
  FI→FISV effective November 11, 2025; unchanged option terms and 100-share delivery.
- [BOX Block notice, OCC 55886](https://boxexchange.com/assets/BOXOnnMemo206943.pdf):
  SQ→XYZ effective January 21, 2025; unchanged terms and 100 Class A shares.

The direct OCC-host captures returned 403; preserved exchange-hosted originals
are at `nn_meta/data_v7/option-rename-notices-20260928/`. Failed capture attempts
remain accounted for. The reviewed declaration is
[V7_REFERENCE_RENAME_REVIEW_20260928.json](../specs/V7_REFERENCE_RENAME_REVIEW_20260928.json).

`reviewed_references.py` adds an exact-pair consumer overlay; it does not mutate
raw responses or the frozen acquisition/validator. Only the underlying name is
normalized, only for the 22 bound provider rows. Dates, source receipts and
notice bytes are bound. All other standard-contract checks remain mandatory.
No automatic extension to other contracts/dates or adjusted roots is allowed.

Compiled review: `nn_meta/validation/v7-reference-rename-review-20260928/`.
Actual consumer readback: `v7-reference-rename-consumer-check-20260928/`.
All 22 originally rejected rows pass the reviewed consumer. Nineteen focused
reference tests passed, including refusal of cash legs, changed strike/size,
unreviewed dates and 404 responses. Downstream consumers must explicitly bind
this new overlay; the original strict audit appropriately retains its verdict.

Nine remaining rejected MSTX rows declare additional USD cash deliverables.
They remain unadmitted to the standard-contract path. The 10,817 unapproved
404 pairs still need recovery/adjudication and impact reconciliation.

## Execution continuation

Another bounded three-contract capture and replay completed while reference
work progressed. Selected paths, quotes and integrated ledger now end in
`20260928-r2`, under their existing validation names. The integrated ledger
preserves all 1,466 earlier events, three decisions and 175 marks, adding ten
marks with unchanged cash. Prefix proof: `v7-integrated-prefix-check-20260928-r2/`.
The next NVDA window is `[1711039350000000000,1711039380000000001)`.
Two of the five retained source cases are complete. Full-universe execution is
still unfinished; this increment does not represent a full path campaign.

## The separate memory failure

The user-reported memory kill was **healys-v6-continual.service**, at
**16:49:07 Central**. It started at 15:45 with two workers and reached a 7.8-GB
peak under MemoryHigh=7 GiB / MemoryMax=8 GiB. systemd-oomd killed the unit.
Service inspection at 17:53 showed failed/oom-kill, Restart=no and zero restarts.
Its next timer attempt was midnight September 29; no manual restart was issued.

Its last progress file still says running, but contains revised-history/new-
lineage errors for AAL, AA, AAOI, AAPL, ABBV, ABNB, ABT, ABVX, ACN and ACHR,
plus changed artifact inputs for ADBE. That file is stale after the kill.
Both compatible input lineage and bounded memory need repair before a useful
retry. This is unrelated to V7 reference completion and does not prove a new
incubator freeze. Journal/progress snapshots are retained under
`nn_meta/validation/v7-completion-v6-oom-observation-20260928/`.
