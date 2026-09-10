# Live taken-position fees

2026-09-10. All work on ops/server-alert-readiness-20260906, isolated from the
home v6 source-pinned build. Taken tracking and exit watcher were deployed;
the user's first real position and supplied fill passed real-data verification.
Actual holdings remain only in server SQLite, not this handoff.

Current change adds broker_fees.py using the linked Robinhood support page
and August 31 PDF fee schedule, checked September 10. Base is $0.04 per
contract per side; add stock/ETF sell SEC/TAF, CAT and applicable index fees.
Account tier is private ROBINHOOD_GOLD environment state. New position contexts
snapshot the fee version/tier. Existing open contexts need a fee-profile
backfill at deployment. No research fees or strategy rules changed.

Entry confirmations and /selllist show estimated entry cost including fees.
SELL WATCH adds fee-aware net P/L only when entry quantity/premium and a fresh
positive option bid are available. Standard retail single-leg, 100 premium
multiplier; estimates allow for unknown execution-level rounding. Commands
now also accept a premium written .09 (leading zero optional).

Validation: full ops suite 668 passed +18 subtests. Tests include the exact
published SPXW fee example, Gold/non-Gold, exchange tiers, penny rounding,
small-order waivers, caps, DOW-stock versus DJX-index classification, and
stale/invalid quote suppression. Sources and scope are in DOCUMENTATION.md.

Deployed d2708d6 at 2026-09-10 04:59 UTC. Private account-tier setting applied
and all active position contexts backfilled with the verified fee profile.
Server entry-cost calculation and Robinhood's published index example passed.
Private queue backup: logs/ops/fee-deploy-20260910T045930Z/taken-before.sqlite3.
No real fills, exit triggers, or research settings changed. Full suite remains
668 passed +18 subtests. /selllist now shows fee-inclusive estimated entry cost.
