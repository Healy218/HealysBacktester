# Handoff — October 3, 2026 — ETFE successor scope

## Selected work

User requested notes and docs for **ETFE — Exchange Traded Funds Expert**, which
replaces active V7 research. Exactly SPY/QQQ/VOO; retain V7 strategies and timing;
restore 1-minute signals and remove 30-minute signals, yielding 1/5/15 minutes.
[Specification](docs/specs/ETFE.md), [TODO](TODO.md),
[ETFE roadmap](ROADMAP.md#etfe--exchange-traded-funds-expert).

## Changes and boundaries

ETFE specification carries inherited strategies, DTE, execution timing, later
midpoint/risk amendments, full features and evaluation discipline. V7 artifacts
remain unchanged. ETFE needs a new catalog/schema/input/evaluation lineage.
No capture, training, provider switch or paper deployment started this session.

TODO now selects ETFE-0 and keeps V7 archive closure as a storage obligation.
The old V7 scientific queue is preserved in
[the TODO snapshot](handoff-history/TODO-2026-10-03-before-etfe.md).
ROADMAP retains V7 gates, adds separate ETFE gates and preserves other workstreams.
README/CURRENT_STATE provide navigation; DECISIONS records the scope change.

## Outstanding user questions and evidence

1. Does Alpaca's start mean its earliest historical options availability or our
   own recording start? Provider documentation says February 2024; exact first
   usable timestamps and complete dependency coverage have not been established.
2. Should the end be the latest completed session at plan freeze or retain
   September 14, 2026? Do not silently freeze an answer or move a running cutoff.
3. Historical option trades/bars are documented; a historical quote-window API
   is not established. V7's observed bid/ask execution and quote features still
   require those observations. Resolve source/coverage before sealing ETFE inputs.

Questions 1–2 were sent to the user; this revision leaves both unresolved.
Read the next user reply as steering this scope. Documentation alone is not
ETFE readiness. Re-declare chronological folds for the changed history and
measure one-minute storage/memory before an expensive campaign.

## V7 preservation obligation

Archive state: `nn_meta/validation/v7-cold-archive-20261002-r0/`.
Destination: `/run/media/healy/MRHA/v7/`, UUID `62C9-C390`.
Archive service: `healys-v7-cold-archive.service`, staged-v2; inspect progress and
VERIFIED/COMPLETE receipts before claiming full completion. Do not restart it
or modify source bindings merely because ETFE is selected.
Local subset complete October 3 at 14:54: all 35,031 eligible files removed;
about 519 GiB free at 15:06. [Audit](docs/reviews/2026-10-03-v7-local-cleanup-complete.json).
Refresh compressed notes and archive docs at full completion. Preserve the
retirement journal, small metadata, shared/raw inputs and MRHA originals.
[Restore guide](docs/reference/V7_COLD_ARCHIVE_README.md).

Preserve unrelated dirty work and .env. Other research/update campaigns remain
paused. This session changes documentation only; no new experiment verdict.
