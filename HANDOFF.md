# Handoff — October 3, 2026 — ETFE initial setup

## Selected work and completed component

User authorized starting ETFE after V7 archive verification. Implemented separate
configuration, parameter catalog, immutable setup manifest, source snapshot,
read-only Alpaca diagnostics and integrity verification. No training/deployment.
[Scope](docs/specs/ETFE.md), [TODO](TODO.md), [review](docs/reviews/2026-10-03-etfe-setup.md).

ETFE is a brand-new expert: SPY/QQQ/VOO, 1/5/15-minute signals, V7 strategy/timing
specifications but no V7 weights/checkpoints or Massive quotes. Historical start
is Alpaca's earliest options availability; end October 2, 2026 inclusive.
Both date preferences are resolved. Verify the first timestamp, not a new choice.

## Selected artifacts

`nn_meta/validation/etfe-setup-20261003-r0/` owns scope.json, catalog.json,
plan.json and PREPARED.json. Plan SHA256:
`8e43d74e2d89d9b3aaaf58d2a65f2acbc713dfa44f19466ee95af5279aa8e707`.
Exact producer/grid sources saved in source-snapshot/ with a hash receipt.
Entry `scripts/prepare_etfe.py` requires NN_META_POOL=etfe and a fresh isolated
output. Existing files are never overwritten. [Commands](docs/reference/ETFE_SETUP.md).
Verify using `./venv/bin/python scripts/verify_etfe_setup.py --setup
nn_meta/validation/etfe-setup-20261003-r0` (one line).

All 20 families, 2,817 parameter variants/timeframe, 8,451 combinations/ticker,
25,353 total. New IDs include ETFE; V7 5/15/30 catalog code remains unchanged.
30 focused tests passed, plus actual source/artifact/probe hash reconciliation.
Every build/training readiness flag remains false; PREPARED is not admission.

## Provider evidence and next steps

- `probe-r1/PROBE.json`: 22 successful-transport GETs, all three stock samples
  and expired references accessible. Historical quotes endpoint returned 404
  for all three examples. Sandbox-failed probe-r0 preserved separately.
- `probe-boundary-r0/BOUNDARY.json`: 21 GETs; January 18, 2024 option trades/bars
  observed in all three ETF samples, earlier than February in public docs.
  Exact global boundary and complete data coverage remain unverified.
- Calendar confirms October 2 stock session 09:30–16:00 New York; option-class
  hours and historical contract/deliverable eligibility remain to be admitted.
- Next ETFE-0 work: resolve historical quote-window availability/methodology
  within Alpaca-only policy; no bars-to-spread substitution, feature dropping,
  archived Massive reuse or silent start-date movement.
- Then bind full input coverage, new ETFE row schema/folds/trials, causal
  strategy/execution evidence and measured memory/disk/recovery before a campaign.

Probe examples are not candidate selection or historical as-of chains; current
expired-reference records and adjusted strikes need dated deliverable evidence.
No subscriptions, broker orders, live streams or bulk capture were started.

## Preserved work

V7 archive is complete on MRHA/v7: 2,847 shards, 325.63 GiB, 35,031 files
reclaimed. [Audit](docs/reviews/2026-10-03-v7-archive-completion-audit.json).
V7 research stays paused; archive Massive quotes are not ETFE inputs. Other
research/update campaigns remain paused. Preserve unrelated dirty work and .env.
