# Handoff — 7-1 closed, live V6 repair prerequisite, September 18, 2026

V7 item 7-1 is complete under the explicit conservative admission policy recorded
in [the closure review](docs/reviews/2026-09-18-v7-6-1-closure.md). The dividend
portion remains sealed and complete. The 234 remaining noncash provider records
now each have one source-bound `explicit_boundary_exclusion` treatment in
`nn_meta/validation/v7-noncash-admission-20260918`.

## 7-1 closure evidence

- 10,428 original corporate-action records partition exactly: 10,194 dividend
  records resolved and 234 noncash records explicitly excluded at their
  boundaries.
- The noncash panel retains every original reference, creates no cash, price
  factor, successor identity, stock deliverable, or option deliverable, and
  excludes 75,781 history rows conservatively.
- `history_admitted=false` and `held_position_admitted=false` are consumed by
  the panel. `require_boundary_safe` rejects a feature or held-position path
  crossing an excluded boundary; pre-boundary history remains usable.
- Focused noncash tests pass. The prior full suite passed 2,338 tests plus 18
  subtests; only the new focused tests were needed for this scoped change.

This closes 7-1 as an admission-policy deliverable. It does not claim that the
economic lifecycle of those corporate actions was observed or settled, and it
does not make V7 research-ready or authorize training.

## Required prerequisite before 7-2

The deployed/live V6 system on the server is the only V6 system that remains in
scope. Its recurring alert path has now been repaired and verified before V7
item 7-2 begins. V6 means the current server model and its live operation, not
a new research build.

The unfinished local short-DTE research build had 21 of 449 symbols complete
and was deleted. No V7 dataset or validation artifact was removed. Its timers
are disabled. The deployed server V6 model, paper operation, and production
policy remain intact.

## Live V6 repair status

The recurring alert path was repaired on September 18. Held-position quote gaps
and the five-minute entry-timing safety stop remain fail-closed (positions are
retained and new entries are withheld), but the server watcher now records those
expected safety stops as degraded instead of sending `[v6] Paper runtime needs
attention`. Genuine runtime and delivery failures remain alertable. The fresh
server watcher check completed healthy after the activation receipt was rebound
to the deployed watcher code. Valid later exits remain separate from these
quote/timing safety stops.

## Current next item: 7-2

With live V6 repair verified, build the complete causal daily/market
context and feature/proposal stores. Use
the admitted history panel and preserve its explicit noncash boundary exclusions.
Do not bridge excluded predecessor/successor identities or invent lifecycle
outcomes. The 7-2 start preflight passed real-shard storage and four-resolution
aggregation checks, but projected naïve full-store output is roughly 396 GB
before inputs and the required 100 GiB reserve. Select and measure a compact
store representation before launching the full build. Items 7-3 through 7-7
remain queued. See [the 7-2 start checkpoint](docs/reviews/2026-09-18-v7-2-start.md).

Work on `main` with scoped commits. V7 datasets remain untouched during the
live V6 repair and this documentation cleanup.
