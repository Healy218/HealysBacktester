# Handoff — September 28, 2026 — V6 full catch-up resumed alongside 7-3

## Focus and stopping point

The user requested V6's full continual update now that V7 downloads are finished,
while continuing gate 7-3. V6 r2 started at 18:17:38 Central and is building the
449-symbol extension through September 28. Three symbols completed with no build
errors at the 18:37 follow-up; no full freeze yet.

## Changes and validation

- Preserved original base, r1 seals and original implementation. New r2 lineage
  rebuilds features/labels against repaired stock history, reusing market captures.
- Verified all 449 stock/context snapshot hashes and pinned the existing September
  28 snapshot. Base dataset hash and active runtime binding remain unchanged.
- Fixed accumulating numerical memo lifetime: one entry prefix, not whole symbol.
  Workers recycle per symbol; two autosized workers, CPU 200%, 11/12-GiB high/max,
  no swap, 12-hour budget capped at next-open-minus-30min.
- Updated installed service. Overnight retries retain unfinished date AND original
  snapshot before advancing to new data. Separate service-exit receipt distinguishes
  external termination from stale progress. Existing timer/market-hours guards stay.
- Twelve focused tests passed, including actual LightGBM training/resume, seals,
  cache release and date/snapshot retry selection. Unit/shell checks passed.
- First completed symbol AAL: 505 candidates, 347 matured, 126 pending, 32 unfilled,
  424.35 seconds. Early service memory approximately 1.46 GiB, peak 1.66 GiB.
  Neither observation proves full-universe runtime or next-day readiness.
- [Recovery evidence](docs/reviews/2026-09-28-v6-continual-recovery.md).

## V7 continuation

Entry and dated-reference captures remain complete; do not restart them.
Reference audit: 2,223,844 pairs, 22 reviewed rename corrections, nine unresolved
cash-deliverable rows and 10,817 unapproved 404s. Bind the reviewed overlay explicitly.
Three more bounded held-path windows added 40,735 bytes. Current path/index/integrated
receipts end `20260928-r3`. Integrated marks rose 185→195, prior fills/decisions/cash
preserved. Two of five source labels complete; full-universe paths remain open.
[Exact pointers](docs/CURRENT_STATE.md), [reference review](docs/reviews/2026-09-28-v7-reference-completion.md).

## Next actions

1. Monitor V6 r2 service, per-symbol progress and latest-run together. Finish all
   symbols, train/evaluate/freeze 40 members; then measure a one-session update.
   No overnight completion guarantee or automatic paper deployment is established.
2. Continue 7-3 reference exception recovery/adjudication and actual held/exit/roll
   frontier work from r3. Full-universe discovery still needs implementation.
3. Observe prospective V6 paper step-order fills/reconciliation. The deployed paper
   runtime and model are unchanged by this research repair.
4. Retain October 2 provider decision and existing FA collection schedules.

## Constraints

Preserve unrelated dirty/untracked work, frozen source hashes and checkpoints.
Selected continual config: `deploy/incubator-continual-v6-r2.json`; root
`incubator/continual-v6/r2/`. Old r1 OOM details remain in the reference review.
Never conflate implemented pipeline, running catch-up, frozen candidate and deployment.
