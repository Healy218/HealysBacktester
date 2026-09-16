# V7 no-OTC scope and preparation checkpoint — September 16, 2026

The user retained Alpaca-only stock data and explicitly excluded OTC work.
BBBY, FRC, REV and SI are removed by issuer identity for the entire research
history. Original captures/membership remain immutable. Scores, ranks and
remaining members are unchanged; no replacement or reranking occurs. Results
will be conditional on this ex-post restriction, not an unrestricted historical
universe or a point-in-time forecast of delisting.

The new immutable universe has 593 tickers, 591 securities and 16,549 research
membership rows. Fifty-one all-history rows were removed (31 in the research
membership window). All retained monthly membership snapshots have listed
exchange codes. Revised plan binds the exact catalog: 11,268 variants per ticker,
6,681,924 combinations. Readiness verifies membership/plan/exclusion hashes.

Eligible-session coverage: 339,640 sessions; 126 original zeros, 67 resolved
aliases and 59 remaining lifecycle/halts. All 59 have retrospective explanations:
41 cash mergers, 14 WBD successor sessions, four halted sessions. Original
Benzinga reports through Alpaca explain VERU's previously unresolved halt.
These cause classifications do not establish executable prices or settlement.

All 1,047 bounded dividend-news requests completed with no failures. The active
4,967 dividend events have 256 narrow exact original-amount headline matches;
4,711 remain unmatched. Article creation/update clocks, currencies, share units,
amounts and source receipts are checked. Effective dates, identity and simultaneous
action units remain separate gates. No current adjustment factors are admitted.

New factorized training fold selection records every retained/excluded row,
purges through settlement, rejects duplicate IDs across shards and requires
exact integer clocks. Bounded multi-shard reads match dense LightGBM predictions
on synthetic tests. Full binned-memory allocation and real training remain open.

Full suite: 1,771 tests and 18 subtests passed, 18 warnings, 83.92s. Log:
`/tmp/v7-no-otc-20260916-tests.log`. Includes existing unrelated dirty V6 work.
The latest readiness check passes input/inventory gates and rejects all eight
missing substantive stages. V7 is not ready. No training/deployment or alerts.

Active paths and next dependencies are in `HANDOFF.md` and
`docs/specs/V7_ACTIVE_INPUTS_20220315.json`.
