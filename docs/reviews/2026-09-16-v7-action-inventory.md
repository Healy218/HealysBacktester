# September 16 V7 full action inventory and DVN cash correction

Built a complete reconciliation of the retained corporate-action captures for
all 594 active stock source/membership symbols, covering the entire requested
March 15, 2022–September 14, 2026 interval. Includes history outside monthly
eligibility because it can enter subsequent feature lookbacks; those action-day
identities remain unassigned until separately reviewed. This is an evidence
inventory, not full-universe adjustment admission. **V7 remains unready.**

## Result

Current artifact `nn_meta/validation/v7-action-inventory-20260916r2`, receipt
`759735a9548add27899d5f4d367ff4cc4c3eafac478338787d0dc817a26d5cb1`:

- 10,380 scoped records, preserving original JSON, payload hashes, provider IDs
  and symbol roles; 5,030 exact symbol/day cash-or-split groups.
- 4,506 matching single-event terms; 354 unreviewed terms; 68 single-provider
  groups; 57 matching totals requiring combined-event review; 45 term mismatches.
- 3,016 groups map to an exact active-session security identity: 2,775 matching
  single events, 149 unreviewed terms, 34 single-provider, 37 combined and 21
  mismatches. No identity extrapolation outside those eligible dates.
- 213 complex records: 78 stock mergers, 48 cash mergers, 47 name changes,
  24 spin-offs, ten stock-and-cash mergers, three unit splits, and one each of
  stock dividend, rights distribution and reorganization. All 47 name changes
  lack explicit effective dates and remain undated; process dates are retained.
- Fifteen simple-event groups coincide with another category or a complex event.
  Roles include old/new/source/acquiree/acquirer and nested stock movements.

The active raw alias GAP adds eight dividend records beyond the older
membership-ticker-only inventory (4,975 Massive dividends versus 4,967).
The captured 119 Massive split-endpoint records include 12 labeled stock
dividends; these stay unreviewed rather than being accepted as simple splits.
Provider-reported ratios remain evidence only: e.g. GE spin-off dates also have
apparent forward-split records, so endpoint categorization alone is insufficient.

`nn_meta/v7/action_inventory.py` compares exact decimal event amounts and ratios;
it ignores cumulative current-share factors. It preserves multiple records,
foreign/unspecified units, incomplete terms and mismatched dates instead of
choosing a provider, deduplicating by equal amount or matching nearest dates.
The CLI checks complete capture counts, original query scopes and input/source
hashes, then seals all records and reconciliation results. Initial r1 is retained;
use r2 with the stock-dividend and query-scope guards.

Alpaca's date filter uses processing dates, and its `all` data-quality option
includes incomplete records. Therefore an absent counterpart does not establish
that no action occurred. Publication timing is separately unproven by these
current captures. [Alpaca endpoint documentation](https://docs.alpaca.markets/us/reference/corporateactions-1)

## Verified DVN exception

The 2024-09-13 DVN event is an actual counterexample to either blindly summing
provider records or trusting a single source. Massive supplies three $0.22
records; Alpaca supplies one. Devon's original August 6 release establishes a
$0.44 distribution, comprising $0.22 fixed and $0.22 variable, payable September
30 to September 13 record holders. PDF pages 1–2 were rendered and visually
reviewed. [Original Devon release](https://investors.devonenergy.com/files/doc_financials/quarterly/2024/q2/Q2-2024-DVN-Earnings-Release.pdf)

Captured raw PDF/announcement:
`nn_meta/data_v7/public-actions-20260916/{dvn-q2-2024-release,dvn-q2-2024-announcement}`.
The PDF redirects to the exact Q4 CDN document linked by the captured issuer
announcement. Request manifest: `v7-dvn-action-evidence-requests-20260916.json`
under validation. Network-denied attempts remain partial; escalated capture
completed, with 203,238 PDF bytes and 44,626 HTML bytes plus receipts.

Immutable review `nn_meta/validation/v7-dvn-action-review-20260916`, receipt
`4eceef5201fdc6948d112c88beb9d74e1789d8d31d35478bb40bf6123e23225c`, identifies all
four provider records and replaces that **entire event group exactly once** with
$0.44. Do not add the correction to existing components. All four records agree
on ex-date; the review does not infer it merely from record date. Both adjacent
active raw-stock rows identify `BBG000BBVJZ8`. Prior Alpaca close is $40.01,
available September 12 at 20:00 UTC; chart factor is 0.9890027493126718, effective
September 13 at 13:30 UTC. Publication uses conservative next-midnight availability.
Full-security action/no-event continuity and downstream integration remain open.
Exact calculation/verification source is retained as `verification.source.txt`.

## Validation and continuation

**1,863 tests +18 subtests passed**, 18 warnings, 93.14 seconds;
`/tmp/v7-action-inventory-tests.log`. Twelve new cases cover original cash units,
ratios, multiple/combined events, nested symbol roles, processing/effective clocks,
foreign/incomplete terms, duplicate IDs and ambiguous active identities.
No source edits followed this passing suite. Full inventory command (exit 0):

```bash
./venv/bin/python scripts/audit_v7_action_inventory.py \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --dividends nn_meta/data_v7/corporate-actions-20260915/dividends \
  --splits nn_meta/data_v7/corporate-actions-20260915/splits \
  --alpaca nn_meta/data_v7/alpaca-actions-20260915 \
  --output nn_meta/validation/v7-action-inventory-20260916r2
```

Log `/tmp/v7-action-inventory-r2.log`. Acquisition quota is now
62,558,635,013 /250,000,000,000 bytes with no reservations. V6 was untouched.
All jobs launched this turn are terminal. Readiness checkpoint
`v7-readiness-20260916-action-inventory.json` still has three passing inventory
checks and eight missing substantive stages. Continue full action/continuity
review, then causal daily/market/sector integration and the quote/physical/
assembly/trial/resource work. Matching terms are not publication proof or an
admitted full history. No training launched.
