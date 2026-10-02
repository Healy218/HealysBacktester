# Handoff — October 2, 2026 — V6 Alpaca provider transition

## User direction

User cancelled Massive options and requested removing it from V6 paper. They
chose preserving all features and the full universe, then explicitly selected
keeping entry readiness blocked pending expanded Alpaca feed capacity. No model
promotion, universe reduction or subscription purchase is authorized.

## Deployed and verified

Scanner v12 / consumer v3 / `v6_alpaca_market_v1.py` deployed 14:20:49 Central.
Drop-in: `99z-alpaca-options-v12.conf`. Source-bound paper manifest SHA:
`72dda355ea27c0e8d355949fc7185e4ce64e88bf2825d635936b7796137ff420`.
The existing broker runtime remains v6 with the ten-minute entry window.

14:23:50: Alpaca held monitoring completed with no errors, 32.687-second run.
Scanner reports `blocked/await_alpaca_feature_coverage`; this is intentional,
not completed new-entry scanning. No Massive network fallback. Historical model,
features, prior catalogue captures and portfolio scope remain preserved. Broker
polling completed at 14:30:02; earlier stale Alpaca quotes remain genuine errors.

## Recorder and blocker

Bounded raw OPRA recorder implemented and tested with quote/trade acknowledgments,
append-only journals, nanosecond timestamps and interruption epochs. The corrected
journal labels direct-WebSocket receipt time explicitly. Bounded probes are not
full feature coverage, not a persistent production recorder and not model admission.

A local census found 2,434 nearest-strike contracts for 414 of 449 securities;
35 prior-date catalogues are absent and strike movement needs extra subscriptions.
Alpaca documents a 1,000 quote-stream limit; the actual 2,434-contract request
was rejected at 14:55:03 with 405 (symbol limit exceeded). No historical option quote endpoint
was found; direct probe returned 404. Live OPRA quotes work. Do not silently
truncate subscriptions, substitute snapshots or discard quote-window features.

Remaining: expanded confirmed capacity, prospective Alpaca catalogues, complete
sealed preceding windows, source/condition/clock mapping and feature/decision
validation, then a versioned entry-adapter admission. See
[provider transition](docs/reviews/2026-10-02-v6-alpaca-provider.md).
Evidence: `nn_meta/validation/v6-alpaca-provider-20261002-r0/`.
47 focused tests and 12 watcher checks passed; corrected recorder tests rerun.

## V7 continues

Resource policy v4 resumed 13:39:30. Original wave seals/checkpoints unchanged.
Selected campaign: `v7-required-inputs-20261002-perf-r0`; discovery supervisor
`finish_v7_discovery_resources_v4.py`, scheduler `run_v7_optimized_campaign_v3.py`.
Up to twelve with dynamic V6/replay/host memory reserves; 7–9 observed workers.

13:39:30–13:54:30: +25,520 decision groups / +2,362,080 assessments, 9.448M/hour.
Remaining original discovery at that short rate is 6.59 continuous days; capture,
replay and incubation pauses are extra. Paper was provider-blocked, so full
co-load remains unproven. [Evidence](docs/reviews/2026-10-02-v7-discovery-concurrency.md).
Committed/pushed `8aaca65`. Gate 7-3 remains open; retain cumulative counts.

Hourly watcher continues here, reporting the deliberate V6 feature block,
held-monitor/broker health and cumulative V7 work. Idle completed incubation and
storage remain omitted. Preserve unrelated dirty work and frozen sources.
