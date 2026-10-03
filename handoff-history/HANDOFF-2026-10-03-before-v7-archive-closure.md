# Handoff — October 3, 2026 — ETFE identity and dates confirmed

## Selected work

ETFE — Exchange Traded Funds Expert — is a brand-new expert. It replaces the
active V7 research priority and uses V7 strategy/timing specifications, not V7
model weights, checkpoints or model identity. Documentation is the selected work.
[Specification](docs/specs/ETFE.md), [TODO](TODO.md),
[roadmap](ROADMAP.md#etfe--exchange-traded-funds-expert).

## Confirmed contract

- Tradable universe: exactly SPY, QQQ, VOO.
- Signal timeframes: 1/5/15 minutes; no 30-minute signals.
- Preserve accepted V7 strategy variants and execution/timing/risk rules.
- Start: Alpaca's earliest historical options availability, not our own recording.
- End: October 2, 2026, inclusive; fixed, not a moving latest-session endpoint.
- Options provider: Alpaca. No Massive quotes, including archived V7 quotes,
  blended quote histories or fallback requests.

The prior two user questions are answered; do not ask them again. ETFE.dates is
closed as a scope decision. No capture, training or runtime changes occurred.
README, specification, ROADMAP, TODO, CURRENT_STATE and DECISIONS agree.

## Next verification work

1. ETFE.history-boundary: verify Alpaca's exact first options timestamp and the
   fixed end-session boundaries using provider/calendar evidence. Documentation
   identifies February 2024, not a sealed exact starting timestamp.
2. ETFE.provider-contract: historical trades/bars do not establish historical
   bid/ask windows. Determine actual Alpaca coverage and document gaps; any
   necessary methodology change must be explicit. Massive is not an option.
3. Before implementation, bind new ETFE catalog/schema/input/fold manifests.
   Preserve causal warmup and complete label horizons; explicitly handle final
   boundary proposals without silently extending beyond October 2.
4. Measure one-minute data/memory/storage demand before expensive campaigns.
   ETFE has its own admission gates; no V7 completion receipt is relabeled.

## Separate V7 preservation obligation

State: `nn_meta/validation/v7-cold-archive-20261002-r0/`.
Destination: `/run/media/healy/MRHA/v7/`, UUID `62C9-C390`.
Archive service: `healys-v7-cold-archive.service`, staged-v2. Inspect current
progress and VERIFIED/COMPLETE receipts before claiming full completion.
Preserve frozen sources and journal; ETFE selection does not restart V7 research.
Local cleanup finished at 14:54 October 3: 35,031 eligible files removed and
about 519 GiB internal free at 15:06.
[Audit](docs/reviews/2026-10-03-v7-local-cleanup-complete.json).
Refresh compressed archive notes at full completion; V7 remains preservation-only.
[Restore guide](docs/reference/V7_COLD_ARCHIVE_README.md).

Preserve unrelated dirty work and .env. Other research/update campaigns remain
paused. No new experiment verdict or model readiness claim from documentation.
